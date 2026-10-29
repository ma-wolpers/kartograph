"""Details-Panel: Symbol-/Farbpunkt-Knöpfe und Legenden, aufgebaut nur bei geänderter Menge.

Früher zerstörte jede Auswahlbewegung alle Knöpfe samt Tooltips und baute
sie neu (~200 ms pro Schritt). Jetzt gilt dasselbe Prinzip wie im
bw-gui ``DataGrid``: Widgets existieren dauerhaft; neu gebaut wird nur, wenn
sich ihre *Menge* ändert (Symbolkatalog, Farbpalette, Spaltenzahl). Ein
Schülerwechsel setzt nur Beschriftung/Zustand — und auch das nur, wenn sich
der Wert unterscheidet.
"""

from __future__ import annotations

from typing import Any

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui


class DetailsButtonsMixin:
    """Mixin: dauerhafte Knöpfe und Legenden des Details-Panels."""

    def _ensure_detail_buttons(self, symbol_cols: int, color_cols: int) -> None:
        """Baut die Knöpfe (neu), wenn sich Katalog, Palette oder Spaltenzahl geändert haben.

        Args:
            symbol_cols: Spalten des Symbol-Knopfrasters.
            color_cols: Spalten des Farbpunkt-Knopfrasters.
        """
        key = (tuple(self.diagnostic_symbol_catalog), tuple(self.color_palette), symbol_cols, color_cols)
        if key == self._detail_buttons_key:
            return
        for frame in (self.symbols_frame, self.colors_frame):
            for child in frame.winfo_children():
                child.destroy()
        self._symbol_buttons = {}
        self._color_buttons = {}
        self._color_marker_buttons = []
        self._widget_options = {}
        tui.Label(self.symbols_frame, text="Symbole").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        for idx, symbol in enumerate(self.diagnostic_symbol_catalog):
            definition = self._symbol_by_meaning.get(symbol)
            shortcut = definition.shortcut if definition else None
            button = tui.Button(self.symbols_frame, command=lambda s=symbol: self._toggle_selected_symbol(s))
            button.grid(row=1 + idx // symbol_cols, column=idx % symbol_cols, sticky="ew", padx=(0, 6), pady=(0, 4))
            self._attach_hover_help(button, label=f"Symbol {symbol} umschalten", shortcut=shortcut.upper() if shortcut else None)
            self._symbol_buttons[symbol] = button
        for col in range(symbol_cols):
            self.symbols_frame.columnconfigure(col, weight=1)
        tui.Label(self.colors_frame, text="Farbpunkte").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        for key_char, color_key, label, hex_color in self.color_palette:
            idx = int(key_char) - 1
            button = ui.Button(self.colors_frame, command=lambda ck=color_key: self._toggle_selected_color(ck),
                               fg=hex_color, padx=6, pady=2)
            button.grid(row=1 + idx // color_cols, column=idx % color_cols, sticky="ew", padx=(0, 6), pady=(0, 4))
            self._attach_hover_help(button, label=f"Farbpunkt {label} umschalten", shortcut=key_char)
            self._color_buttons[color_key] = (button, label)
            self._color_marker_buttons.append(button)
        for col in range(color_cols):
            self.colors_frame.columnconfigure(col, weight=1)
        self._apply_color_button_theme()
        self._detail_buttons_key = key

    def _update_detail_buttons(self, student: Any) -> None:
        """Setzt Beschriftung/Zustand aller Knöpfe für *student* (nur geänderte Werte).

        Args:
            student: Ausgewählter Schüler.
        """
        for symbol, button in self._symbol_buttons.items():
            count = int(student.diagnostic.symbols.get(symbol, 0))
            icon = self._symbol_glyph(symbol)
            self._set_widget_options(button, text=f"{icon} {symbol}" if count == 0 else f"{icon} {symbol} x{count}")
        for color_key, (button, label) in self._color_buttons.items():
            active = color_key in student.diagnostic.color_tags
            self._set_widget_options(button, text=f"{label}*" if active else label, relief="sunken" if active else "raised")

    def _set_legend_lines(self, frame: Any, lines: list[str]) -> None:
        """Ersetzt die Legenden-Labels in *frame* nur, wenn sich die Zeilen geändert haben.

        Args:
            frame: ``symbol_legend_frame`` oder ``color_legend_frame``.
            lines: Anzuzeigende Zeilen (leer = Legende leeren).
        """
        key = str(frame)
        if self._legend_lines.get(key) == lines:
            return
        for child in frame.winfo_children():
            child.destroy()
        for line in lines:
            tui.Label(frame, text=line, wraplength=self._details_legend_wraplength(), justify="left").pack(anchor="w")
        self._legend_lines[key] = list(lines)

    def _set_widget_options(self, widget: Any, **options: Any) -> None:
        """``configure`` nur mit den Optionen, deren Wert sich seit dem letzten Setzen geändert hat.

        Args:
            widget: Knopf des Details-Panels.
            **options: Gewünschte Optionen.
        """
        applied = self._widget_options.setdefault(str(widget), {})
        changed = {name: value for name, value in options.items() if applied.get(name) != value}
        if changed:
            widget.configure(**changed)
            applied.update(changed)
