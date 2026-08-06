"""Renderer für die Legendenseite im PDF-Export (v4-Modell).

Erzeugt Symboltabellen und Farbmarkierungslegende als ReportLab-Platypus-
Elemente und verteilt sie über eine oder mehrere PDF-Seiten.
"""

from __future__ import annotations

from xml.sax.saxutils import escape as xml_escape

from app.core.domain.models_v4 import SeatingPlan
from app.infrastructure.exporters.pdf_font_utils import build_symbol_token, order_color_keys
from app.infrastructure.symbol_config_loader import SymbolDefinition


class PdfLegendRenderer:
    """Zeichnet die Legendenseite(n) eines PDF-Sitzplans.

    Enthält Tabellen für Symboldefinitionen und Farbpunktbedeutungen.
    Der Symbolzeichensatz muss nach Fontregistrierung per ``set_symbol_font``
    gesetzt werden.
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

    def _legend_symbol_tables(
        self, used_symbol_levels: dict[str, set[int]]
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        """Gibt je eine Tabelle pro Symbolbedeutung zurück (Titel + Zeilen).

        Args:
            used_symbol_levels: Aus dem Planexport gesammelte Stärken pro Symbol.

        Returns:
            Liste von (Bedeutung, [(Token, Legendentext), ...]).
        """
        symbol_keys: list[str] = []
        for symbol in self._symbol_definitions:
            if symbol.meaning in used_symbol_levels:
                symbol_keys.append(symbol.meaning)
        for meaning in sorted(used_symbol_levels.keys(), key=str.lower):
            if meaning not in self._symbols_by_meaning:
                symbol_keys.append(meaning)

        tables: list[tuple[str, list[tuple[str, str]]]] = []
        for meaning in symbol_keys:
            counts = sorted(used_symbol_levels.get(meaning, set()), reverse=True)
            if not counts:
                continue
            definition = self._symbols_by_meaning.get(meaning)
            rows: list[tuple[str, str]] = []
            for count in counts:
                token = build_symbol_token(meaning, count, self._symbols_by_meaning, self._symbol_font_uses_fallback)
                legend_text = definition.legend_for_count(count) if definition else meaning
                rows.append((token, legend_text))
            tables.append((meaning, rows))
        return tables

    def _build_legend_table(self, colors, title: str, rows: list[tuple[str, str]], available_w: float, token_is_markup: bool):
        """Erstellt ein ReportLab-Platypus-Table-Objekt für eine Legendentabelle.

        Args:
            colors: ReportLab ``colors``-Modul.
            title: Tabellenüberschrift.
            rows: Zeilen als (Token, Beschreibung).
            available_w: Verfügbare Breite in Punkten.
            token_is_markup: True, wenn Token-Zellen XML-Markup enthalten.

        Returns:
            Konfiguriertes ReportLab ``Table``-Objekt.
        """
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Table, TableStyle

        token_col_w = min(92.0, max(74.0, available_w * 0.16))
        text_col_w = available_w - token_col_w

        header_style = ParagraphStyle("LHdr", fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=TA_LEFT, wordWrap="CJK")
        token_font = "Helvetica" if token_is_markup else self._symbol_font_name
        token_style = ParagraphStyle("LTok", fontName=token_font, fontSize=10, leading=12, alignment=TA_LEFT, wordWrap="CJK")
        text_style = ParagraphStyle("LTxt", fontName="Helvetica", fontSize=9, leading=12, alignment=TA_LEFT, wordWrap="CJK")

        data = [[Paragraph("", header_style), Paragraph(xml_escape(title), header_style)]]
        for token, text in rows:
            token_cell = token if token_is_markup else xml_escape(token)
            data.append([Paragraph(token_cell, token_style), Paragraph(xml_escape(text), text_style)])

        table = Table(data, colWidths=[token_col_w, text_col_w], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]))
        return table

    def _draw_wrapped_legend_table(
        self, c, colors, page_w: float, page_h: float, y: float,
        title: str, rows: list[tuple[str, str]], *, token_is_markup: bool = False,
    ) -> float:
        """Platziert eine Legendentabelle und verteilt sie über Seiten.

        Args:
            c: ReportLab-Canvas.
            colors: ReportLab ``colors``-Modul.
            page_w: Seitenbreite in Punkten.
            page_h: Seitenhöhe in Punkten.
            y: Aktuelle Y-Position (Oberkante des freien Bereichs).
            title: Tabellenüberschrift.
            rows: Tabellenzeilen.
            token_is_markup: True wenn Token-Spalte XML-Markup enthält.

        Returns:
            Neue Y-Position nach dem Zeichnen der Tabelle.
        """
        margin = 50.0
        available_w = min(page_w - 2 * margin, page_w * 0.78)
        table = self._build_legend_table(colors, title, rows, available_w, token_is_markup)

        pieces = table.split(available_w, max(10.0, y - margin))
        if not pieces:
            c.showPage()
            y = page_h - margin
            pieces = table.split(available_w, max(10.0, y - margin))
            if not pieces:
                return y

        for index, piece in enumerate(pieces):
            _pw, piece_height = piece.wrap(available_w, max(10.0, y - margin))
            if piece_height > y - margin:
                c.showPage()
                y = page_h - margin
                _pw, piece_height = piece.wrap(available_w, max(10.0, y - margin))
            piece.drawOn(c, margin, y - piece_height)
            y -= piece_height
            if index < len(pieces) - 1:
                c.showPage()
                y = page_h - margin

        return y - 12.0

    def render_legend_page(
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
        """Zeichnet die Legendenseite(n) auf das Canvas.

        Startet mit ``c.showPage()`` eine neue Seite und zeichnet dann
        Symboltabellen und ggf. Farbpunkte.

        Args:
            c: ReportLab-Canvas.
            colors: ReportLab ``colors``-Modul.
            page_w: Seitenbreite in Punkten.
            page_h: Seitenhöhe in Punkten.
            plan: Sitzplan (für Farbpunktbedeutungen).
            used_symbol_levels: Gesammelte Symbolstärken aus dem Plan-Render.
            used_colors: Gesammelte Farbschlüssel aus dem Plan-Render.
            include_color_markers: Farbpunktlegende zeichnen.
        """
        c.showPage()
        margin = 36.0
        y = page_h - margin
        has_content = False

        for title, rows in self._legend_symbol_tables(used_symbol_levels):
            y = self._draw_wrapped_legend_table(c, colors, page_w, page_h, y, title, rows)
            has_content = True

        if include_color_markers and used_colors:
            color_rows: list[tuple[str, str]] = []
            for color_key in order_color_keys(list(used_colors), self._color_order):
                palette_entry = plan.color_palette.get(color_key)
                meaning = str(palette_entry.meaning if palette_entry else "").strip()
                if not meaning:
                    continue
                label, hex_color = self._color_by_key.get(color_key, (color_key, "#999999"))
                try:
                    colors.HexColor(hex_color)
                    safe_hex = hex_color
                except Exception:
                    safe_hex = "#999999"
                token_markup = f"<font color='{safe_hex}'>&#9679;</font> {xml_escape(label)}"
                color_rows.append((token_markup, meaning))
            if color_rows:
                y = self._draw_wrapped_legend_table(
                    c, colors, page_w, page_h, y, "Farbpunkte", color_rows, token_is_markup=True
                )
                has_content = True

        if not has_content:
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 10)
            c.drawString(margin, y, "Keine Legendeninhalte fuer die gewaehlte Exportauswahl vorhanden.")
