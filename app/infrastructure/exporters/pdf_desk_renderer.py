"""Renderer für einzelne Schülertische im PDF-Export (v4-Modell).

Zeichnet Polygon, Farbpunkte, Noten, Namen und Symbole für jeden Tisch
auf ein ReportLab-Canvas. Symbolzeichensatz und Fallback-Modus werden nach
der Fontregistrierung über ``set_symbol_font`` gesetzt.
"""

from __future__ import annotations

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.table_groups import SeatGeometryV4
from app.core.usecases.v4.grade_usecases import compute_grade_display
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols
from app.infrastructure.exporters.pdf_font_utils import (
    build_symbol_token,
    fit_multi_line_font,
    fit_single_line_font,
    iter_symbol_counts,
    order_color_keys,
)
from app.infrastructure.symbol_config_loader import SymbolDefinition


class PdfDeskRenderer:
    """Zeichnet einzelne Schülertische auf ein ReportLab-Canvas.

    Muss nach der Fontregistrierung über ``set_symbol_font`` aktualisiert
    werden, damit Symbole mit dem korrekten Zeichensatz ausgegeben werden.
    """

    def __init__(
        self,
        symbol_definitions: list[SymbolDefinition],
        color_palette: list[tuple[str, str, str, str]] | None = None,
    ) -> None:
        """Initialisiert den Renderer mit Symboldefinitionen und Farbpalette.

        Args:
            symbol_definitions: Geordnete Liste aller Symboldefinitionen.
            color_palette: Farbpalette als Liste von (key, color_key, label, hex).
        """
        self._symbol_definitions = symbol_definitions
        self._symbols_by_meaning: dict[str, SymbolDefinition] = {
            item.meaning: item for item in symbol_definitions
        }
        self._color_order = [color_key for _key, color_key, _label, _hex in (color_palette or [])]
        self._color_by_key = {
            color_key: (label, hex_color)
            for _key, color_key, label, hex_color in (color_palette or [])
        }
        self._symbol_font_name = "Helvetica"
        self._symbol_font_uses_fallback = True

    def set_symbol_font(self, font_name: str, uses_fallback: bool) -> None:
        """Setzt den Zeichensatz für Symbolglyphen nach der Fontregistrierung.

        Args:
            font_name: Registrierter ReportLab-Fontname.
            uses_fallback: True, wenn kein Unicode-Font gefunden wurde.
        """
        self._symbol_font_name = font_name
        self._symbol_font_uses_fallback = uses_fallback

    def render_desk(
        self,
        c,
        colors,
        pdfmetrics,
        seat: SeatGeometryV4,
        polygon: tuple[tuple[float, float], ...],
        center: tuple[float, float],
        cell_size: float,
        export_plan: SeatingPlan,
        grade_mode: str,
        visible_symbols: set[str] | None,
        include_color_markers: bool,
        used_symbol_levels: dict[str, set[int]],
        used_colors: set[str],
    ) -> None:
        """Zeichnet einen einzelnen Tisch auf das Canvas.

        Für Lehrertische wird nur der Umriss mit Beschriftung gezeichnet.
        Schülertische erhalten ggf. Farbpunkte, Namen, Noten und Symbole.
        Die Dicts *used_symbol_levels* und *used_colors* werden in-place
        mit den auf diesem Tisch verwendeten Werten aktualisiert (für die
        Legende).

        Args:
            c: ReportLab-Canvas.
            colors: ReportLab ``colors``-Modul.
            pdfmetrics: ReportLab ``pdfmetrics``-Modul.
            seat: Geometrie samt Schüler (oder ``None`` bei Lehrertisch).
            polygon: Eckpunkte in PDF-Koordinaten.
            center: Mittelpunkt in PDF-Koordinaten.
            cell_size: Zellenbreite in Punkten (beeinflusst Schriftgröße).
            export_plan: Plan (für Notenberechnung).
            grade_mode: ``"none"``, ``"final_only"`` oder ``"include_provisional"``.
            visible_symbols: Sichtbare Symbole; None = alle.
            include_color_markers: Farbpunkte zeichnen.
            used_symbol_levels: Wird mit Symbolstärken befüllt (für Legende).
            used_colors: Wird mit Farbschlüsseln befüllt (für Legende).
        """
        pixel_points: list[float] = []
        px_values: list[float] = []
        py_values: list[float] = []
        for world_x, world_y in polygon:
            pixel_points.extend((world_x, world_y))
            px_values.append(world_x)
            py_values.append(world_y)

        center_x, center_y = center
        box_left = min(px_values)
        box_right = max(px_values)
        box_top = min(py_values)
        box_bottom = max(py_values)
        box_width = box_right - box_left
        box_height = box_bottom - box_top

        c.setFillColor(colors.white)
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.8 if seat.is_teacher else 1.3)
        path = c.beginPath()
        path.moveTo(pixel_points[0], pixel_points[1])
        for idx in range(2, len(pixel_points), 2):
            path.lineTo(pixel_points[idx], pixel_points[idx + 1])
        path.close()
        c.drawPath(path, fill=1, stroke=1)

        if seat.is_teacher:
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", max(8, int(min(box_width, box_height) * 0.16)))
            c.drawCentredString(center_x, center_y + min(box_width, box_height) * 0.05, "Lehrertisch")
            return

        student = seat.student
        c.setFillColor(colors.black)
        first_name = (student.first_name or "").strip()
        last_name = (student.last_name or "").strip()
        student_name = (
            f"{first_name} {last_name}".strip() if (first_name and last_name) else (first_name or last_name)
        )

        if grade_mode == "include_provisional":
            overall_grade = compute_grade_display(export_plan, student.student_id, allow_provisional=True)
        elif grade_mode == "final_only":
            overall_grade = compute_grade_display(export_plan, student.student_id, allow_provisional=False)
        else:
            overall_grade = ""

        if overall_grade:
            c.setFont("Helvetica-Bold", max(6, int(min(box_width, box_height) * 0.12)))
            c.drawString(box_left + box_width * 0.08, box_top + box_height * 0.16, overall_grade)

        if include_color_markers and student.diagnostic.color_tags:
            desk_color_markers = order_color_keys(list(student.diagnostic.color_tags), self._color_order)
            radius = max(3.0, min(box_width, box_height) * 0.035)
            spacing = radius * 2.0 + 3.0
            start_dot_x = center_x + box_width * 0.18
            dots_y = box_top + box_height * 0.18
            for idx, color_key in enumerate(desk_color_markers[:9]):
                _label, hex_color = self._color_by_key.get(color_key, (color_key, "#999999"))
                try:
                    fill_color = colors.HexColor(hex_color)
                except Exception:
                    fill_color = colors.HexColor("#999999")
                c.setFillColor(fill_color)
                c.setStrokeColor(colors.black)
                c.circle(start_dot_x + idx * spacing, dots_y, radius, stroke=1, fill=1)
                used_colors.add(color_key)
            c.setFillColor(colors.black)
            c.setStrokeColor(colors.black)

        effective_symbols = summarize_latest_symbols(export_plan, student.student_id)
        source_symbols = effective_symbols if effective_symbols else student.diagnostic.symbols
        symbol_entries = iter_symbol_counts(
            self._symbol_definitions, self._symbols_by_meaning, source_symbols, visible_symbols
        )
        lines: list[str] = []
        line_tokens: list[str] = []
        used_slots = 0
        for meaning, count in symbol_entries:
            used_symbol_levels.setdefault(meaning, set()).add(count)
            token = build_symbol_token(meaning, count, self._symbols_by_meaning, self._symbol_font_uses_fallback)
            if line_tokens and used_slots + len(token) > 6:
                lines.append(" ".join(line_tokens))
                line_tokens = [token]
                used_slots = len(token)
            else:
                line_tokens.append(token)
                used_slots += len(token)
        if line_tokens:
            lines.append(" ".join(line_tokens))

        max_text_width = box_width * 0.88
        content_bottom = box_top + box_height * 0.12
        content_top = box_top + box_height * 0.88
        content_height = max(0.0, content_top - content_bottom)

        name_area_height = 0.0
        if student_name and lines:
            name_area_height = content_height * 0.34
        elif student_name:
            name_area_height = content_height * 0.7

        if student_name:
            name_font = fit_single_line_font(
                pdfmetrics, "Helvetica-Bold", student_name, max_text_width,
                max(10.0, name_area_height * 0.9), min_size=8,
                max_size=max(10, int(cell_size * 0.28)),
            )
            c.setFont("Helvetica-Bold", name_font)
            c.drawCentredString(center_x, content_top - name_font, student_name)

        if not lines:
            return

        symbol_top = content_top - name_area_height - (cell_size * 0.03 if student_name else 0.0)
        symbol_height = max(0.0, symbol_top - content_bottom)
        line_font, line_height = fit_multi_line_font(
            pdfmetrics, self._symbol_font_name, lines, max_text_width, symbol_height,
            min_size=7, max_size=max(9, int(cell_size * 0.24)),
        )
        c.setFont(self._symbol_font_name, line_font)
        for idx, line in enumerate(lines):
            c.drawCentredString(center_x, symbol_top - line_font - idx * line_height, line)
