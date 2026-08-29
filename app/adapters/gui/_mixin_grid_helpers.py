"""Grid-Hilfsmethoden-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Enthält die Zeichenlogik für Schülertisch-Inhalte (Farbpunkte, Note, Name, Symbole),
die Namensformatierung, Symbol-Glyphen-Rendering und Hilfsmethoden für das
Details-Panel (Spaltenanzahl, Legende, Farb-/Symbol-Zeilen).
"""

from __future__ import annotations

from app.core.domain.effective_symbol import resolve_symbol_display
from app.core.domain.models_v4 import ParticipationRating, SeatingPlan, Student
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import fonts


class GridHelpersMixin:
    """Mixin: Schülertisch-Inhaltszeichnung und Grid-Darstellungs-Hilfsmethoden (v4)."""

    def _draw_student_desk_content(
        self,
        student: Student,
        center_px: float,
        min_px: float,
        min_py: float,
        theme: dict,
        student_name_font_size: int,
        today_session,
        latest_symbols_by_student: dict,
        overall_grade_by_student: dict,
    ) -> None:
        """Zeichnet Farbpunkte, Gesamtnote, Schülername und Symbole in einen Schülertisch.

        Args:
            student: Schüler, dessen Tisch-Inhalt gezeichnet wird.
            center_px: Horizontale Pixel-Mitte des Tisches.
            min_px: Linke Pixel-Kante des Tisches.
            min_py: Obere Pixel-Kante des Tisches.
            theme: Aktuelles Farb-/Theme-Dictionary für das Zeichnen.
            student_name_font_size: Schriftgröße für den Schülernamen.
            today_session: Vorberechnete heutige Session (einmal pro Redraw
                statt pro Schüler neu gesucht, s. ``_mixin_grid_render.py``).
            latest_symbols_by_student: Vorberechnete neueste Symbole je Schüler.
            overall_grade_by_student: Vorberechnete Gesamtnoten-Anzeige je Schüler.
        """
        main_text = self._display_names.get(student.student_id, "")
        effective_symbols = self._effective_grid_symbols_v4(
            student, latest_symbols_by_student.get(student.student_id, {}), today_session,
        )
        participation_today = self._participation_rating_today(student, today_session)
        symbol_lines = self._symbol_grid_lines(effective_symbols, participation_today)
        desk_color_markers = self._ordered_color_markers(student.diagnostic.color_tags)

        if desk_color_markers:
            radius = max(3, int(self.cell_size * 0.03))
            spacing = radius * 2 + 3
            start_x_dot = center_px + self.cell_size * 0.17
            circles_y = min_py + self.cell_size * 0.12
            for idx, color_key in enumerate(desk_color_markers[:9]):
                _label, hex_color = self._color_by_key.get(color_key, (color_key, "#999999"))
                cx = start_x_dot + idx * spacing
                self.canvas.create_oval(
                    cx - radius, circles_y - radius, cx + radius, circles_y + radius,
                    fill=hex_color, outline=theme["border"], width=1, tags=("grid",),
                )

        overall_grade = overall_grade_by_student.get(student.student_id, "")
        if overall_grade:
            self.canvas.create_text(
                min_px + self.cell_size * 0.08, min_py + self.cell_size * 0.09,
                text=overall_grade, fill=theme["fg_muted"],
                font=("Segoe UI", max(6, int(self.cell_size * 0.085)), "bold"),
                anchor="nw", tags=("grid",),
            )

        if main_text:
            self.canvas.create_text(
                center_px, min_py + self.cell_size * 0.24,
                text=main_text, fill=theme["fg_primary"],
                font=("Segoe UI", student_name_font_size, "bold"), tags=("grid",),
            )

        if symbol_lines:
            available_h = self.cell_size * 0.56
            raw_symbol_font = int(available_h / max(1, len(symbol_lines)) - 1)
            symbol_font = max(5, min(int(self.cell_size * 0.09), raw_symbol_font))
            symbol_size, symbol_weight = self._symbol_font_style(symbol_font)
            line_height = max(symbol_size + 2, 6)
            symbols_start_y = min_py + self.cell_size * 0.42
            for idx, line in enumerate(symbol_lines):
                self.canvas.create_text(
                    center_px, symbols_start_y + idx * line_height,
                    text=line, fill=theme["fg_muted"],
                    font=("Segoe UI", symbol_size, symbol_weight), tags=("grid",),
                )

    def _symbol_font_style(self, base_size: int) -> tuple[int, str]:
        """Berechnet Schriftgröße und -gewicht für Symbol-Glyphen.

        Args:
            base_size: Ausgangsschriftgröße vor Anpassung durch ``symbol_strength``.
        """
        if self.symbol_strength <= 0:
            return base_size, "normal"
        if self.symbol_strength == 1:
            return base_size + 1, "bold"
        return base_size + 2, "bold"

    def _compute_uniform_student_name_font_size(self) -> int:
        """Berechnet die größte Schriftgröße, bei der alle Schülernamen in die Zelle passen."""
        base_size = max(8, int(self.cell_size * 0.12))
        min_size = 5
        max_text_width = int(self.cell_size * 0.88)

        labels = [label for label in self._display_names.values() if label]
        if not labels:
            return base_size

        size = base_size
        while size > min_size:
            font = fonts.Font(family="Segoe UI", size=size, weight="bold")
            if all(font.measure(label) <= max_text_width for label in labels):
                return size
            size -= 1
        return min_size

    def _symbol_glyph(self, symbol_name: str) -> str:
        """Gibt die Glyph-Zeichenkette für ein Symbol zurück.

        Prüft zuerst den eingebauten Katalog (``self._symbol_by_meaning``,
        unverändert), dann eigene Doku-Symbole des aktuellen Plans über
        ``resolve_symbol_display()`` — deren Fallback greift auch für
        historische Einträge, deren eigenes Symbol inzwischen gelöscht wurde.

        Args:
            symbol_name: Name (eingebaute Bedeutung) bzw. ID (eigenes Symbol)
                des gesuchten Symbols.
        """
        symbol = self._symbol_by_meaning.get(symbol_name)
        if symbol is not None:
            return symbol.glyph
        glyph, _display_name = resolve_symbol_display(symbol_name, self.effective_documentation_symbols)
        return glyph

    def _iter_symbol_counts(self, symbols: dict[str, int]) -> list[tuple[str, int]]:
        """Erstellt eine geordnete Liste von (symbol_name, count)-Paaren.

        Args:
            symbols: Dictionary von Symbolname zu Anzahl.
        """
        entries: list[tuple[str, int]] = []
        for symbol_name in self.symbol_catalog:
            count = int(symbols.get(symbol_name, 0))
            if count >= 1:
                entries.append((symbol_name, min(3, count)))
        for symbol_name, raw_count in sorted(symbols.items()):
            if symbol_name not in self.symbol_catalog:
                count = int(raw_count)
                if count >= 1:
                    entries.append((symbol_name, min(3, count)))
        return entries

    def _symbol_grid_lines(
        self, symbols: dict[str, int], participation: ParticipationRating | None = None
    ) -> list[str]:
        """Erstellt Zeilen mit Symbol-Glyphen für die Rasterdarstellung (max 6 Glyphen/Zeile).

        Args:
            symbols: Dictionary von Symbolname zu Anzahl.
            participation: Heutige Mitarbeit-Bewertung ("+"/"o"/"-"/"☆"), falls gesetzt.
                Erscheint als führendes Token vor den Symbol-Glyphen.
        """
        entries = self._iter_symbol_counts(symbols)
        if not entries and not participation:
            return []
        lines: list[str] = []
        line_tokens: list[str] = []
        used_slots = 0
        if participation:
            # Bewertung ist immer genau EIN visueller Token (+, o, -, ☆), unabhängig
            # von ihrer String-Laenge in Python -- bewusst nicht len(participation),
            # das waere nur zufaellig korrekt (alle vier Werte sind ein Codepoint)
            # und wuerde die eigentliche Absicht verschleiern.
            line_tokens.append(participation)
            used_slots = 1
        for symbol_name, count in entries:
            token = self._symbol_glyph(symbol_name) * count
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
        return lines

    def _symbol_legend_lines(self, symbols: dict[str, int]) -> list[str]:
        """Erstellt Legendenzeilen im Format ``"Glyph Legendentext"`` für ein Symbol-Dictionary.

        Args:
            symbols: Dictionary von Symbolname zu Anzahl.
        """
        if not symbols:
            return []
        lines: list[str] = []
        for symbol_name, count in self._iter_symbol_counts(symbols):
            glyph = self._symbol_glyph(symbol_name)
            definition = self._symbol_by_meaning.get(symbol_name)
            if definition is not None:
                legend_text = definition.legend_for_count(count)
            else:
                _glyph, legend_text = resolve_symbol_display(symbol_name, self.effective_documentation_symbols)
            lines.append(f"{glyph * count} {legend_text}".strip())
        return lines

    def _ordered_color_markers(self, color_markers: list[str]) -> list[str]:
        """Gibt die Farbpunkte in der konfigurierten Palettenreihenfolge zurück.

        Args:
            color_markers: Liste der Farb-Schlüssel eines Schülers (unsortiert).
        """
        ordered: list[str] = []
        seen: set[str] = set()
        configured_order = [color_key for _key, color_key, _label, _hex_color in self.color_palette]
        for color_key in configured_order:
            if color_key in color_markers and color_key not in seen:
                ordered.append(color_key)
                seen.add(color_key)
        for color_key in color_markers:
            if color_key not in seen:
                ordered.append(color_key)
                seen.add(color_key)
        return ordered

    def _color_legend_lines(self, plan: SeatingPlan, desk_color_markers: list[str]) -> list[str]:
        """Erstellt Legendenzeilen für Farbpunkte (v4: color_palette statt color_meanings).

        Args:
            plan: Sitzplan, dessen ``color_palette`` für die Bedeutungen genutzt wird.
            desk_color_markers: Farb-Schlüssel des betroffenen Schülertisches.
        """
        lines: list[str] = []
        for color_key in self._ordered_color_markers(desk_color_markers):
            entry = plan.color_palette.get(color_key)
            meaning = entry.meaning if entry else ""
            if not meaning:
                continue
            label, _hex_color = self._color_by_key.get(color_key, (color_key, "#999999"))
            lines.append(f"● {label}: {meaning}")
        return lines

    def _details_button_columns(self) -> int:
        """Gibt die Anzahl der Spalten für Symbol- und Farb-Buttons im Details-Panel zurück."""
        return 2 if self.details_overlay_position in {"left", "right"} else 5

    def _details_legend_wraplength(self) -> int:
        """Gibt die maximale Textbreite für Legende-Labels im Details-Panel zurück."""
        return 500 if self.details_overlay_position in {"left", "right"} else 980

    def _effective_grid_symbols_v4(
        self, student: Student, latest_symbols: dict[str, int], today_session,
    ) -> dict[str, int]:
        """Gibt die für das Raster relevanten Symbole eines Schülers zurück (v4).

        Args:
            student: Schüler, dessen Raster-Symbole ermittelt werden.
            latest_symbols: Neueste Symbole dieses Schülers, vorberechnet für
                ALLE Schüler in einem Durchlauf (``summarize_latest_symbols_by_student``,
                s. ``_mixin_grid_render.py``) statt hier erneut pro Schüler
                die Sessions neu zu sortieren. Leeres Dict, wenn keine vorliegen.
            today_session: Die heutige Session (einmal pro Redraw vorberechnet
                statt pro Schüler erneut per Datum gesucht), oder ``None``.
        """
        if not self.current_plan:
            return {
                k: v for k, v in student.diagnostic.symbols.items()
                if k in self._grid_visible_symbols
            }

        source = latest_symbols if latest_symbols else dict(student.diagnostic.symbols)
        effective = {
            k: v for k, v in source.items()
            if k not in self._documentation_only_symbols
            if k in self._grid_visible_symbols
        }

        # Add today's documentation-only symbols
        if today_session and student.is_named():
            today_entry = today_session.entry_for(student.student_id)
            if today_entry:
                for k, v in today_entry.symbols.items():
                    if k not in self._documentation_only_symbols:
                        continue
                    if k not in self._grid_visible_symbols:
                        continue
                    effective[k] = int(v)

        return effective

    def _participation_rating_today(self, student: Student, today_session) -> ParticipationRating | None:
        """Gibt die heutige Mitarbeit-Bewertung eines Schülers zurück, falls gesetzt.

        Bewusst über ``entry.participation`` statt ``entry.symbols`` -- kein
        Vermischen mit dem Symbolsystem (siehe ``ParticipationRating``).

        Args:
            student: Schüler, dessen heutige Bewertung ermittelt wird.
            today_session: Die heutige Session (einmal pro Redraw vorberechnet,
                s. ``_effective_grid_symbols_v4``), oder ``None``.
        """
        if not student.is_named() or today_session is None:
            return None
        entry = today_session.entry_for(student.student_id)
        return entry.participation if entry else None
