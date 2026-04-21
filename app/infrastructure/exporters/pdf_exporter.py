from __future__ import annotations

from pathlib import Path

from app.core.domain.models import SeatingPlan
from app.infrastructure.symbol_config_loader import SymbolDefinition


class PdfSeatingPlanExporter:
    def __init__(self, symbol_definitions: list[SymbolDefinition]):
        self._symbols_by_meaning = {item.meaning: item for item in symbol_definitions}

    def export_plan(self, plan: SeatingPlan, output_path: Path, orientation_mode: str) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.pdfgen import canvas
        except Exception as exc:
            raise RuntimeError("PDF-Export benoetigt reportlab (pip install reportlab).") from exc

        if orientation_mode not in {"teacher_bottom", "teacher_top"}:
            raise ValueError("Unbekannter Exportmodus")

        desks = []
        for desk in plan.desks:
            x, y = desk.x, desk.y
            if orientation_mode == "teacher_top":
                x, y = -x, -y
            desks.append((x, y, desk))

        if not desks:
            raise ValueError("Plan enthaelt keine Tische")

        min_x = min(x for x, _y, _desk in desks)
        max_x = max(x for x, _y, _desk in desks)
        min_y = min(y for _x, y, _desk in desks)
        max_y = max(y for _x, y, _desk in desks)

        cols = max_x - min_x + 1
        rows = max_y - min_y + 1

        page_w, page_h = landscape(A4)
        margin = 30.0
        title_h = 20.0
        usable_w = page_w - 2 * margin
        usable_h = page_h - 2 * margin - title_h
        cell_size = min(usable_w / max(1, cols), usable_h / max(1, rows))

        c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))
        c.setTitle(plan.name)

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, page_h - margin + 2, f"Sitzplan: {plan.name}")

        top_y = page_h - margin - title_h

        for x, y, desk in desks:
            draw_x = margin + (x - min_x) * cell_size
            draw_y = top_y - (y - min_y + 1) * cell_size

            if desk.desk_type == "teacher":
                c.setFillColor(colors.HexColor("#9A6A24"))
                c.setStrokeColor(colors.HexColor("#7A521B"))
                border = 1.8
            else:
                c.setFillColor(colors.HexColor("#DBEAFE"))
                c.setStrokeColor(colors.HexColor("#1D4ED8"))
                border = 1.2

            c.setLineWidth(border)
            c.rect(draw_x, draw_y, cell_size, cell_size, fill=1, stroke=1)

            if desk.desk_type == "teacher":
                c.setFillColor(colors.white)
                c.setFont("Helvetica-Bold", max(6, int(cell_size * 0.11)))
                c.drawCentredString(draw_x + cell_size / 2, draw_y + cell_size * 0.55, "Lehrertisch")
                continue

            c.setFillColor(colors.black)
            name_font = max(6, int(cell_size * 0.1))
            c.setFont("Helvetica-Bold", name_font)
            student_name = (desk.student_name or "Schuelertisch").strip()
            max_name_chars = max(4, int(cell_size / max(5, name_font * 0.55)))
            if len(student_name) > max_name_chars:
                student_name = student_name[: max_name_chars - 1] + "…"
            c.drawCentredString(draw_x + cell_size / 2, draw_y + cell_size * 0.78, student_name)

            lines: list[str] = []
            for meaning, count in sorted(desk.symbols.items(), key=lambda item: item[0].lower()):
                symbol = self._symbols_by_meaning.get(meaning)
                if symbol is None:
                    glyph = "•"
                    legend = meaning
                else:
                    glyph = symbol.glyph
                    legend = symbol.legend_for_count(int(count))

                repeated = glyph * max(1, min(3, int(count)))
                lines.append(f"{repeated} {legend}".strip())

            if not lines:
                continue

            available_h = cell_size * 0.5
            raw_font = int(available_h / max(1, len(lines)) - 1)
            line_font = max(4, min(int(cell_size * 0.08), raw_font))
            line_height = max(line_font + 1, 5)
            start_y = draw_y + cell_size * 0.62 - line_height

            c.setFont("Helvetica", line_font)
            for idx, line in enumerate(lines):
                max_chars = max(4, int((cell_size * 0.9) / max(4, line_font * 0.55)))
                clipped = line if len(line) <= max_chars else line[: max_chars - 1] + "…"
                c.drawCentredString(draw_x + cell_size / 2, start_y - idx * line_height, clipped)

        c.showPage()
        c.save()
