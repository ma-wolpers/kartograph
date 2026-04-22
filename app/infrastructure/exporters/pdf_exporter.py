from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from app.core.domain.models import SeatingPlan
from app.core.domain.table_groups import build_desk_geometries, normalize_tablegroups_in_place
from app.infrastructure.symbol_config_loader import SymbolDefinition


class PdfSeatingPlanExporter:
    def __init__(self, symbol_definitions: list[SymbolDefinition]):
        self._symbol_definitions = symbol_definitions
        self._symbols_by_meaning = {item.meaning: item for item in symbol_definitions}
        self._symbol_font_name = "Helvetica"
        self._symbol_font_uses_fallback = True

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

    def _iter_symbol_counts(self, symbols: dict[str, int]) -> list[tuple[str, int]]:
        entries: list[tuple[str, int]] = []

        for symbol in self._symbol_definitions:
            count = int(symbols.get(symbol.meaning, 0))
            if count < 1:
                continue
            entries.append((symbol.meaning, min(3, count)))

        for meaning, raw_count in sorted(symbols.items(), key=lambda item: item[0].lower()):
            if meaning in self._symbols_by_meaning:
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

    def export_plan(self, plan: SeatingPlan, output_path: Path, orientation_mode: str) -> None:
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

            lines: list[str] = []
            line_tokens: list[str] = []
            used_slots = 0
            for meaning, count in self._iter_symbol_counts(desk.symbols):
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

        c.showPage()
        c.save()
