"""Orchestriert den PDF-Export eines Sitzplans.

Koordiniert Fontregistrierung, Geometrieberechnung, Tischrendering
(via PdfDeskRenderer) und Legendenseite (via PdfLegendRenderer).
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Literal

from app.core.domain.models import SeatingPlan
from app.core.domain.table_groups import build_desk_geometries, normalize_tablegroups_in_place
from app.infrastructure.exporters.pdf_desk_renderer import PdfDeskRenderer
from app.infrastructure.exporters.pdf_legend_renderer import PdfLegendRenderer
from app.infrastructure.symbol_config_loader import SymbolDefinition

GradeDisplayMode = Literal["none", "final_only", "include_provisional"]


class PdfSeatingPlanExporter:
    """Exportiert einen Sitzplan als PDF-Datei (A4 quer).

    Nutzt ReportLab für die Ausgabe. Symbole werden mit einem Unicode-Font
    gerendert, falls einer der unterstützten Systemfonts verfügbar ist;
    andernfalls wird auf Buchstabenkürzel ausgewichen.
    """

    _FONT_CANDIDATES = [
        ("SegoeUISymbol", Path("C:/Windows/Fonts/seguisym.ttf")),
        ("SegoeUIEmoji", Path("C:/Windows/Fonts/seguiemj.ttf")),
        ("DejaVuSans", Path("C:/Windows/Fonts/DejaVuSans.ttf")),
        ("ArialUnicodeMS", Path("C:/Windows/Fonts/ARIALUNI.TTF")),
    ]

    def __init__(
        self,
        symbol_definitions: list[SymbolDefinition],
        color_palette: list[tuple[str, str, str, str]] | None = None,
    ) -> None:
        """Initialisiert den Exporter.

        Args:
            symbol_definitions: Geordnete Liste aller Symboldefinitionen.
            color_palette: Farbpalette als Liste von (key, color_key, label, hex).
        """
        self._desk_renderer = PdfDeskRenderer(symbol_definitions, color_palette)
        self._legend_renderer = PdfLegendRenderer(symbol_definitions, color_palette)
        self._symbol_font_registered = False

    def _ensure_symbol_font(self, pdfmetrics, ttfonts) -> None:
        """Registriert den besten verfügbaren Unicode-Font für Symbole.

        Wird einmalig pro Export-Aufruf ausgeführt. Wird kein Font gefunden,
        bleibt Helvetica (Fallback) aktiv.

        Args:
            pdfmetrics: ReportLab ``pdfmetrics``-Modul.
            ttfonts: ReportLab ``ttfonts``-Modul.
        """
        if self._symbol_font_registered:
            return
        self._symbol_font_registered = True
        for font_name, font_path in self._FONT_CANDIDATES:
            try:
                if not font_path.exists():
                    continue
                pdfmetrics.registerFont(ttfonts.TTFont(font_name, str(font_path)))
                self._desk_renderer.set_symbol_font(font_name, uses_fallback=False)
                self._legend_renderer.set_symbol_font(font_name, uses_fallback=False)
                return
            except Exception:
                continue

    def export_plan(
        self,
        plan: SeatingPlan,
        output_path: Path,
        orientation_mode: str,
        *,
        grade_mode: GradeDisplayMode = "none",
        visible_symbols: set[str] | None = None,
        include_color_markers: bool = False,
        include_legend_page: bool = False,
    ) -> None:
        """Exportiert *plan* als PDF nach *output_path*.

        Args:
            plan: Zu exportierender Sitzplan.
            output_path: Zieldatei (wird überschrieben).
            orientation_mode: ``"teacher_bottom"`` oder ``"teacher_top"``.
            grade_mode: Notenmodus für die PDF-Ausgabe.
            visible_symbols: Zu exportierende Symbole; None = alle.
            include_color_markers: Farbpunkte an Tischen zeichnen.
            include_legend_page: Legendenseite anhängen.

        Raises:
            RuntimeError: Wenn reportlab nicht installiert ist.
            ValueError: Bei ungültigem Modus oder leerem Plan.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.pdfbase import pdfmetrics, ttfonts
            from reportlab.pdfgen import canvas
        except Exception as exc:
            raise RuntimeError("PDF-Export benoetigt reportlab (pip install reportlab).") from exc

        self._ensure_symbol_font(pdfmetrics, ttfonts)

        if orientation_mode not in {"teacher_bottom", "teacher_top"}:
            raise ValueError("Unbekannter Exportmodus")
        if grade_mode not in {"none", "final_only", "include_provisional"}:
            raise ValueError("Unbekannter Notenmodus")

        export_plan = deepcopy(plan)
        normalize_tablegroups_in_place(export_plan)
        geometries = build_desk_geometries(export_plan)
        if not geometries:
            raise ValueError("Plan enthaelt keine Tische")

        all_points: list[tuple[float, float]] = []
        render_items: list[tuple[tuple[tuple[float, float], ...], tuple[float, float], object]] = []
        for geometry in geometries:
            points = list(geometry.polygon)
            cx, cy = geometry.center_x, geometry.center_y
            if orientation_mode == "teacher_top":
                points = [(-px, -py) for px, py in points]
                cx, cy = -cx, -cy
            polygon = tuple(points)
            render_items.append((polygon, (cx, cy), geometry.desk))
            all_points.extend(points)

        min_x = min(p[0] for p in all_points)
        max_x = max(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_y = max(p[1] for p in all_points)
        span_x = max(0.1, max_x - min_x)
        span_y = max(0.1, max_y - min_y)

        page_w, page_h = landscape(A4)
        margin = 30.0
        title_h = 20.0
        usable_w = page_w - 2 * margin
        usable_h = page_h - 2 * margin - title_h
        cell_size = min(usable_w / span_x, usable_h / span_y)
        grid_w = span_x * cell_size
        origin_x = margin + max(0.0, (usable_w - grid_w) / 2)
        top_y = page_h - margin - title_h

        c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))
        c.setTitle(export_plan.name)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, page_h - margin + 2, f"Sitzplan: {export_plan.name}")

        used_symbol_levels: dict[str, set[int]] = {}
        used_colors: set[str] = set()

        for polygon, center, desk in render_items:
            pdf_polygon = tuple(
                (origin_x + (wx - min_x) * cell_size, top_y - (wy - min_y) * cell_size)
                for wx, wy in polygon
            )
            pdf_center = (
                origin_x + (center[0] - min_x) * cell_size,
                top_y - (center[1] - min_y) * cell_size,
            )
            self._desk_renderer.render_desk(
                c, colors, pdfmetrics, desk, pdf_polygon, pdf_center, cell_size,
                export_plan, grade_mode, visible_symbols, include_color_markers,
                used_symbol_levels, used_colors,
            )

        if include_legend_page:
            self._legend_renderer.render_legend_page(
                c, colors, page_w, page_h, export_plan, used_symbol_levels, used_colors, include_color_markers
            )

        c.showPage()
        c.save()
