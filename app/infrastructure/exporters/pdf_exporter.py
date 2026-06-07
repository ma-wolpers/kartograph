from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape as xml_escape

from app.core.domain.models import SeatingPlan
from app.core.domain.table_groups import build_desk_geometries, normalize_tablegroups_in_place
from app.core.usecases.plan_usecases import compute_grade_display_for_student, summarize_latest_symbols_for_student
from app.infrastructure.symbol_config_loader import SymbolDefinition

GradeDisplayMode = Literal["none", "final_only", "include_provisional"]


class PdfSeatingPlanExporter:
    def __init__(
        self,
        symbol_definitions: list[SymbolDefinition],
        color_palette: list[tuple[str, str, str, str]] | None = None,
    ):
        self._symbol_definitions = symbol_definitions
        self._symbols_by_meaning = {item.meaning: item for item in symbol_definitions}
        self._symbol_font_name = "Helvetica"
        self._symbol_font_uses_fallback = True
        self._color_order = [color_key for _key, color_key, _label, _hex_color in (color_palette or [])]
        self._color_by_key = {
            color_key: (label, hex_color)
            for _key, color_key, label, hex_color in (color_palette or [])
        }

    def _ensure_symbol_font(self, pdfmetrics, ttfonts) -> None:
        if self._symbol_font_name != "Helvetica":
            return

        font_candidates = [
            ("SegoeUISymbol", Path("C:/Windows/Fonts/seguisym.ttf")),
            ("SegoeUIEmoji", Path("C:/Windows/Fonts/seguiemj.ttf")),
            ("DejaVuSans", Path("C:/Windows/Fonts/DejaVuSans.ttf")),
            ("ArialUnicodeMS", Path("C:/Windows/Fonts/ARIALUNI.TTF")),
        ]
        for font_name, font_path in font_candidates:
            try:
                if not font_path.exists():
                    continue
                pdfmetrics.registerFont(ttfonts.TTFont(font_name, str(font_path)))
                self._symbol_font_name = font_name
                self._symbol_font_uses_fallback = False
                return
            except Exception:
                continue

    def _iter_symbol_counts(
        self,
        symbols: dict[str, int],
        visible_symbols: set[str] | None = None,
    ) -> list[tuple[str, int]]:
        entries: list[tuple[str, int]] = []

        for symbol in self._symbol_definitions:
            if visible_symbols is not None and symbol.meaning not in visible_symbols:
                continue
            count = int(symbols.get(symbol.meaning, 0))
            if count < 1:
                continue
            entries.append((symbol.meaning, min(3, count)))

        for meaning, raw_count in sorted(symbols.items(), key=lambda item: item[0].lower()):
            if meaning in self._symbols_by_meaning:
                continue
            if visible_symbols is not None and meaning not in visible_symbols:
                continue
            count = int(raw_count)
            if count < 1:
                continue
            entries.append((meaning, min(3, count)))

        return entries

    def _symbol_token(self, meaning: str, count: int) -> str:
        symbol = self._symbols_by_meaning.get(meaning)
        if symbol is None:
            return "?" * max(1, min(3, int(count)))

        clamped_count = max(1, min(3, int(count)))
        if self._symbol_font_uses_fallback:
            shortcut = (symbol.shortcut or meaning[:1] or "?").upper()
            return shortcut * clamped_count
        return symbol.glyph * clamped_count

    def _fit_single_line_font(
        self,
        pdfmetrics,
        font_name: str,
        text: str,
        max_width: float,
        max_height: float,
        min_size: int,
        max_size: int,
    ) -> int:
        if not text:
            return min_size
        for size in range(max_size, min_size - 1, -1):
            text_width = pdfmetrics.stringWidth(text, font_name, size)
            text_height = size * 1.15
            if text_width <= max_width and text_height <= max_height:
                return size
        return min_size

    def _fit_multi_line_font(
        self,
        pdfmetrics,
        font_name: str,
        lines: list[str],
        max_width: float,
        max_height: float,
        min_size: int,
        max_size: int,
    ) -> tuple[int, float]:
        if not lines:
            return min_size, max(6.0, min_size * 1.1)

        for size in range(max_size, min_size - 1, -1):
            line_height = max(6.0, size * 1.12)
            total_height = line_height * len(lines)
            if total_height > max_height:
                continue
            too_wide = any(pdfmetrics.stringWidth(line, font_name, size) > max_width for line in lines)
            if not too_wide:
                return size, line_height

        fallback_height = max(6.0, min_size * 1.1)
        return min_size, fallback_height

    def _ordered_color_keys(self, color_markers: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        for color_key in self._color_order:
            if color_key in color_markers and color_key not in seen:
                ordered.append(color_key)
                seen.add(color_key)

        for color_key in color_markers:
            if color_key in seen:
                continue
            ordered.append(color_key)
            seen.add(color_key)

        return ordered

    def _legend_symbol_keys(self, used_symbol_levels: dict[str, set[int]]) -> list[str]:
        keys: list[str] = []
        for symbol in self._symbol_definitions:
            if symbol.meaning in used_symbol_levels:
                keys.append(symbol.meaning)

        for meaning in sorted(used_symbol_levels.keys(), key=lambda item: item.lower()):
            if meaning in self._symbols_by_meaning:
                continue
            keys.append(meaning)

        return keys

    def _legend_symbol_tables(self, used_symbol_levels: dict[str, set[int]]) -> list[tuple[str, list[tuple[str, str]]]]:
        tables: list[tuple[str, list[tuple[str, str]]]] = []

        for meaning in self._legend_symbol_keys(used_symbol_levels):
            counts = sorted(used_symbol_levels.get(meaning, set()), reverse=True)
            if not counts:
                continue

            definition = self._symbols_by_meaning.get(meaning)
            rows: list[tuple[str, str]] = []
            for count in counts:
                token = self._symbol_token(meaning, count)
                if definition is None:
                    legend_text = meaning
                else:
                    legend_text = definition.legend_for_count(count)
                rows.append((token, legend_text))

            tables.append((meaning, rows))

        return tables

    def _legend_color_rows(self, plan: SeatingPlan, used_colors: set[str]) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        for color_key in self._ordered_color_keys(list(used_colors)):
            meaning = str(plan.color_meanings.get(color_key) or "").strip()
            if not meaning:
                continue
            label, hex_color = self._color_by_key.get(color_key, (color_key, "#999999"))
            rows.append((label, hex_color, meaning))
        return rows

    def _draw_wrapped_legend_table(
        self,
        c,
        colors,
        page_w: float,
        page_h: float,
        y_start: float,
        title: str,
        rows: list[tuple[str, str]],
        *,
        token_is_markup: bool = False,
    ) -> float:
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Table, TableStyle

        margin = 36.0
        available_w = min(page_w - 2 * margin, page_w * 0.78)
        token_col_w = min(92.0, max(74.0, available_w * 0.16))
        text_col_w = available_w - token_col_w

        header_style = ParagraphStyle(
            "LegendHeader",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
        token_font_name = "Helvetica" if token_is_markup else self._symbol_font_name
        token_style = ParagraphStyle(
            "LegendToken",
            fontName=token_font_name,
            fontSize=10,
            leading=12,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
        text_style = ParagraphStyle(
            "LegendText",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )

        data = [[Paragraph("", header_style), Paragraph(xml_escape(title), header_style)]]
        for token, text in rows:
            token_cell = token if token_is_markup else xml_escape(token)
            data.append(
                [
                    Paragraph(token_cell, token_style),
                    Paragraph(xml_escape(text), text_style),
                ]
            )

        table = Table(data, colWidths=[token_col_w, text_col_w], repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        )

        y = y_start
        pieces = table.split(available_w, max(10.0, y - margin))
        if not pieces:
            c.showPage()
            y = page_h - margin
            pieces = table.split(available_w, max(10.0, y - margin))
            if not pieces:
                return y

        for index, piece in enumerate(pieces):
            piece_width, piece_height = piece.wrap(available_w, max(10.0, y - margin))
            if piece_height > y - margin:
                c.showPage()
                y = page_h - margin
                piece_width, piece_height = piece.wrap(available_w, max(10.0, y - margin))
            piece.drawOn(c, margin, y - piece_height)
            y -= piece_height

            if index < len(pieces) - 1:
                c.showPage()
                y = page_h - margin

        return y - 12.0

    def _draw_legend_page(
        self,
        c,
        colors,
        page_w: float,
        page_h: float,
        plan: SeatingPlan,
        used_symbol_levels: dict[str, set[int]],
        used_colors: set[str],
        include_color_markers: bool,
    ) -> None:
        c.showPage()

        margin = 36.0
        y = page_h - margin
        has_content = False

        symbol_tables = self._legend_symbol_tables(used_symbol_levels)
        for title, rows in symbol_tables:
            y = self._draw_wrapped_legend_table(c, colors, page_w, page_h, y, title, rows)
            has_content = True

        if include_color_markers and used_colors:
            color_rows = self._legend_color_rows(plan, used_colors)
            if color_rows:
                table_rows: list[tuple[str, str]] = []
                for label, hex_color, meaning in color_rows:
                    try:
                        colors.HexColor(hex_color)
                        safe_hex = hex_color
                    except Exception:
                        safe_hex = "#999999"
                    token_markup = f"<font color='{safe_hex}'>&#9679;</font> {xml_escape(label)}"
                    table_rows.append((token_markup, meaning))

                y = self._draw_wrapped_legend_table(
                    c,
                    colors,
                    page_w,
                    page_h,
                    y,
                    "Farbpunkte",
                    table_rows,
                    token_is_markup=True,
                )
                has_content = True

        if not has_content:
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 10)
            c.drawString(margin, y, "Keine Legendeninhalte fuer die gewaehlte Exportauswahl vorhanden.")

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

        render_items: list[tuple[tuple[tuple[float, float], ...], tuple[float, float], object]] = []
        all_points: list[tuple[float, float]] = []

        for geometry in geometries:
            points = list(geometry.polygon)
            center_x = geometry.center_x
            center_y = geometry.center_y

            if orientation_mode == "teacher_top":
                points = [(-px, -py) for px, py in points]
                center_x = -center_x
                center_y = -center_y

            polygon = tuple(points)
            render_items.append((polygon, (center_x, center_y), geometry.desk))
            all_points.extend(points)

        min_x = min(point[0] for point in all_points)
        max_x = max(point[0] for point in all_points)
        min_y = min(point[1] for point in all_points)
        max_y = max(point[1] for point in all_points)

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

        c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))
        c.setTitle(export_plan.name)

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, page_h - margin + 2, f"Sitzplan: {export_plan.name}")

        top_y = page_h - margin - title_h
        used_symbol_levels: dict[str, set[int]] = {}
        used_colors: set[str] = set()

        for polygon, center, desk in render_items:
            pixel_points: list[float] = []
            px_values: list[float] = []
            py_values: list[float] = []
            for world_x, world_y in polygon:
                px = origin_x + (world_x - min_x) * cell_size
                py = top_y - (world_y - min_y) * cell_size
                pixel_points.extend((px, py))
                px_values.append(px)
                py_values.append(py)

            center_x = origin_x + (center[0] - min_x) * cell_size
            center_y = top_y - (center[1] - min_y) * cell_size

            box_left = min(px_values)
            box_right = max(px_values)
            box_top = min(py_values)
            box_bottom = max(py_values)
            box_width = box_right - box_left
            box_height = box_bottom - box_top

            c.setFillColor(colors.white)
            c.setStrokeColor(colors.black)
            border = 1.8 if desk.desk_type == "teacher" else 1.3
            c.setLineWidth(border)
            path = c.beginPath()
            path.moveTo(pixel_points[0], pixel_points[1])
            for idx in range(2, len(pixel_points), 2):
                path.lineTo(pixel_points[idx], pixel_points[idx + 1])
            path.close()
            c.drawPath(path, fill=1, stroke=1)

            if desk.desk_type == "teacher":
                c.setFillColor(colors.black)
                c.setFont("Helvetica-Bold", max(8, int(min(box_width, box_height) * 0.16)))
                c.drawCentredString(center_x, center_y + min(box_width, box_height) * 0.05, "Lehrertisch")
                continue

            c.setFillColor(colors.black)
            student_name = (desk.student_name or "").strip()

            if grade_mode == "include_provisional":
                overall_grade = compute_grade_display_for_student(export_plan, desk.x, desk.y, allow_provisional=True)
            elif grade_mode == "final_only":
                overall_grade = compute_grade_display_for_student(export_plan, desk.x, desk.y, allow_provisional=False)
            else:
                overall_grade = ""

            if overall_grade:
                c.setFont("Helvetica-Bold", max(6, int(min(box_width, box_height) * 0.12)))
                c.drawString(box_left + box_width * 0.08, box_top + box_height * 0.16, overall_grade)

            desk_color_markers = self._ordered_color_keys(list(desk.color_markers))
            if include_color_markers and desk_color_markers:
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

                    cx = start_dot_x + idx * spacing
                    c.setFillColor(fill_color)
                    c.setStrokeColor(colors.black)
                    c.circle(cx, dots_y, radius, stroke=1, fill=1)
                    used_colors.add(color_key)
                c.setFillColor(colors.black)
                c.setStrokeColor(colors.black)

            effective_symbols = summarize_latest_symbols_for_student(export_plan, desk.x, desk.y)
            source_symbols = effective_symbols if effective_symbols else desk.symbols

            lines: list[str] = []
            line_tokens: list[str] = []
            used_slots = 0
            for meaning, count in self._iter_symbol_counts(source_symbols, visible_symbols):
                used_symbol_levels.setdefault(meaning, set()).add(count)
                token = self._symbol_token(meaning, count)
                token_slots = len(token)
                if line_tokens and used_slots + token_slots > 6:
                    lines.append(" ".join(line_tokens))
                    line_tokens = [token]
                    used_slots = token_slots
                else:
                    line_tokens.append(token)
                    used_slots += token_slots
            if line_tokens:
                lines.append(" ".join(line_tokens))

            max_text_width = box_width * 0.88
            content_bottom = box_top + box_height * 0.12
            content_top = box_top + box_height * 0.88
            content_height = max(0.0, content_top - content_bottom)
            has_name = bool(student_name)
            has_symbols = bool(lines)

            name_area_height = 0.0
            if has_name and has_symbols:
                name_area_height = content_height * 0.34
            elif has_name:
                name_area_height = content_height * 0.7

            if has_name:
                max_name_font = max(10, int(cell_size * 0.28))
                name_font = self._fit_single_line_font(
                    pdfmetrics,
                    "Helvetica-Bold",
                    student_name,
                    max_text_width,
                    max(10.0, name_area_height * 0.9),
                    min_size=8,
                    max_size=max_name_font,
                )
                c.setFont("Helvetica-Bold", name_font)
                name_baseline = content_top - name_font
                c.drawCentredString(center_x, name_baseline, student_name)

            if not has_symbols:
                continue

            symbol_top = content_top - name_area_height - (cell_size * 0.03 if has_name else 0.0)
            symbol_height = max(0.0, symbol_top - content_bottom)

            max_symbol_font = max(9, int(cell_size * 0.24))
            line_font, line_height = self._fit_multi_line_font(
                pdfmetrics,
                self._symbol_font_name,
                lines,
                max_text_width,
                symbol_height,
                min_size=7,
                max_size=max_symbol_font,
            )

            c.setFont(self._symbol_font_name, line_font)
            start_y = symbol_top - line_font
            for idx, line in enumerate(lines):
                c.drawCentredString(center_x, start_y - idx * line_height, line)

        if include_legend_page:
            self._draw_legend_page(
                c,
                colors,
                page_w,
                page_h,
                export_plan,
                used_symbol_levels,
                used_colors,
                include_color_markers,
            )

        c.showPage()
        c.save()
