"""Orchestriert den PDF-Export eines Sitzplans (v4-Modell).

Koordiniert Fontregistrierung, Geometrieberechnung, Tischrendering
(via PdfDeskRenderer) und Legendenseite (via PdfLegendRenderer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.domain.grade_display_mode import (
    DEFAULT_GRADE_DISPLAY_MODE,
    GradeDisplayMode,
    is_grade_display_mode,
)
from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.pdf_view_mode import is_pdf_view_mode, orientations_for
from app.core.domain.permanent_absence import active_students, apply_export_visibility
from app.core.domain.seat_orientation import orient_geometries, orientation_label, world_bounds
from app.core.domain.settings import DEFAULT_NAME_FORMAT
from app.core.domain.student_naming import compute_display_names
from app.core.domain.table_groups import build_seat_geometries_v4
from app.core.usecases.v4.tablegroup_usecases import normalize_tablegroups
from app.infrastructure.exporters.pdf_desk_renderer import PdfDeskRenderer
from app.infrastructure.exporters.pdf_legend_renderer import PdfLegendRenderer
from app.infrastructure.symbol_config_loader import SymbolDefinition

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
        view_mode: str,
        *,
        grade_mode: GradeDisplayMode = DEFAULT_GRADE_DISPLAY_MODE,
        visible_symbols: set[str] | None = None,
        include_color_markers: bool = False,
        include_legend_page: bool = False,
        name_format: str = DEFAULT_NAME_FORMAT,
        disambiguate_colliding_names: bool = False,
    ) -> None:
        """Exportiert *plan* als PDF nach *output_path*.

        Eine Einzelansicht ergibt eine Seite A4 quer; ``BOTH_ON_ONE_PAGE`` eine
        Seite A4 hochkant mit beiden Ansichten übereinander (Reihenfolge aus
        ``pdf_view_mode.orientations_for``), getrennt durch eine gestrichelte
        Schnittlinie, jede Kopie mit eigener Titelzeile.

        Args:
            plan: Zu exportierender Sitzplan.
            output_path: Zieldatei (wird überschrieben).
            view_mode: PDF-Ansicht aus ``pdf_view_mode.PDF_VIEW_MODES``.
            grade_mode: Notenmodus für die PDF-Ausgabe.
            visible_symbols: Zu exportierende Symbole; None = alle.
            include_color_markers: Farbpunkte an Tischen zeichnen.
            include_legend_page: Legendenseite anhängen.
            name_format: Namensformat (eines der ``NAME_FORMAT_OPTIONS``), wie
                für Grid und Sitzplan-Vorschau.
            disambiguate_colliding_names: Bei gleichen Vornamen automatisch so
                viel vom Nachnamen ergänzen, bis eindeutig (siehe
                ``compute_display_names()``).

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

        if not is_pdf_view_mode(view_mode):
            raise ValueError("Unbekannter Exportmodus")
        if not is_grade_display_mode(grade_mode):
            raise ValueError("Unbekannter Notenmodus")

        export_plan = normalize_tablegroups(plan)
        geometries = apply_export_visibility(export_plan, build_seat_geometries_v4(export_plan))
        if not geometries:
            raise ValueError("Plan enthaelt keine Tische")

        orientations = orientations_for(view_mode)
        single = len(orientations) == 1
        page_w, page_h = landscape(A4) if single else A4
        if single:
            areas = [_PlanArea(_MARGIN, page_h - _MARGIN, page_w - 2 * _MARGIN, page_h - 2 * _MARGIN)]
        else:
            half = page_h / 2
            areas = [
                _PlanArea(_MARGIN, page_h - _MARGIN, page_w - 2 * _MARGIN, page_h - _MARGIN - half - _CUT_GAP),
                _PlanArea(_MARGIN, half - _CUT_GAP - _TITLE_H, page_w - 2 * _MARGIN, half - _CUT_GAP - _TITLE_H - _MARGIN),
            ]

        c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))
        c.setTitle(export_plan.meta.name)
        context = _DeskContext(
            colors, pdfmetrics, export_plan, grade_mode, visible_symbols, include_color_markers,
            used_symbol_levels={}, used_colors=set(),
            display_names=compute_display_names(
                active_students(export_plan.classroom.students), name_format, disambiguate_colliding_names
            ),
        )
        for orientation, area in zip(orientations, areas):
            title = f"Sitzplan: {export_plan.meta.name}"
            if not single:
                title += f" – {orientation_label(orientation)}"
            self._render_plan_block(c, geometries, orientation, area, title, context)
        if not single:
            c.setDash(4, 3)
            c.line(_MARGIN, page_h / 2, page_w - _MARGIN, page_h / 2)
            c.setDash()

        used_symbol_levels, used_colors = context.used_symbol_levels, context.used_colors
        if include_legend_page:
            self._legend_renderer.render_legend_page(
                c, colors, page_w, page_h, export_plan, used_symbol_levels, used_colors, include_color_markers
            )

        c.showPage()
        c.save()

    def _render_plan_block(self, c, geometries, orientation: str, area: "_PlanArea", title: str, context: "_DeskContext") -> None:
        """Zeichnet Titel und eine Ansicht des Plans in *area* (eine Kopie auf der Seite).

        Der Titel steht knapp über ``area.top``; darunter wird der Plan
        gleichmäßig skaliert, horizontal zentriert und oben angelegt.

        Args:
            c: ReportLab-Canvas.
            geometries: Ungedrehte Sitzgeometrien (``build_seat_geometries_v4``).
            orientation: Ansicht-Schlüssel aus ``ORIENTATION_MODES``.
            area: Zielbereich auf der Seite (PDF-Koordinaten, y nach oben).
            title: Titelzeile der Kopie.
            context: Gemeinsame Renderdaten aller Kopien (sammelt genutzte Symbole/Farben).
        """
        render_items = orient_geometries(geometries, orientation)
        bounds = world_bounds(item.polygon for item in render_items)
        usable_h = area.height - _TITLE_H
        cell_size = min(area.width / bounds.span_x, usable_h / bounds.span_y)
        origin_x = area.left + max(0.0, (area.width - bounds.span_x * cell_size) / 2)
        top_y = area.top - _TITLE_H

        c.setFont("Helvetica-Bold", 12)
        c.drawString(area.left, area.top + 2, title)

        def to_pdf(wx: float, wy: float) -> tuple[float, float]:
            return origin_x + (wx - bounds.min_x) * cell_size, top_y - (wy - bounds.min_y) * cell_size

        for item in render_items:
            self._desk_renderer.render_desk(
                c, context.colors, context.pdfmetrics, item.geometry,
                tuple(to_pdf(wx, wy) for wx, wy in item.polygon), to_pdf(*item.center), cell_size,
                context.plan, context.grade_mode, context.visible_symbols, context.include_color_markers,
                context.used_symbol_levels, context.used_colors, context.display_names,
            )


_MARGIN = 30.0
"""Seitenrand in Punkt."""
_TITLE_H = 20.0
"""Höhe, die unter einer Titelzeile für den Plan freibleibt."""
_CUT_GAP = 10.0
"""Abstand jeder Kopie zur Schnittlinie in der Seitenmitte (Doppelansicht)."""


@dataclass(frozen=True)
class _PlanArea:
    """Bereich einer Plan-Kopie auf der Seite; Titel steht knapp über ``top``."""

    left: float
    top: float
    width: float
    height: float


@dataclass
class _DeskContext:
    """Renderdaten, die alle Kopien einer Seite teilen (genutzte Symbole/Farben für die Legende)."""

    colors: Any
    pdfmetrics: Any
    plan: SeatingPlan
    grade_mode: GradeDisplayMode
    visible_symbols: set[str] | None
    include_color_markers: bool
    used_symbol_levels: dict[str, set[int]] = field(default_factory=dict)
    used_colors: set[str] = field(default_factory=set)
    display_names: dict = field(default_factory=dict)
