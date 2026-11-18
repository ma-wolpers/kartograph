"""Symbolsicht des Kartograph-Hauptfensters: einzige Stelle, an der die GUI ihre Symbol-Lookups ableitet.

Quelle ist :class:`~app.core.domain.symbol_view.SymbolView` (programmweiter
Katalog + Kompetenzen + eigene Symbole des offenen Plans).
:meth:`SymbolCatalogMixin._apply_symbol_view_if_changed` baut sie neu, sobald
sich Katalog, Kompetenzen oder die eigenen Symbole des Plans ändern, und leitet
daraus *alle* GUI-Lookups ab (``symbol_definitions``, ``symbol_catalog``,
``diagnostic_symbol_catalog``, ``_symbol_by_meaning``, ``competences_by_id``,
``effective_documentation_symbols``, Raster-Filter, PDF-Exporter). Ändert sich der
programmweite Katalog zur Laufzeit, werden Kürzel-Leiste und Detail-Knöpfe neu
aufgebaut; Tastenkürzel lösen ohnehin live über die Sicht auf.
"""

from __future__ import annotations

from app.core.domain.grid_symbol_filter import visible_grid_symbols
from app.core.domain.symbol_view import SymbolView, build_symbol_view
from app.infrastructure.exporters.pdf_exporter import PdfSeatingPlanExporter


class SymbolCatalogMixin:
    """Mixin: hält die Symbolsicht und alle daraus abgeleiteten Lookups aktuell."""

    def _init_symbol_catalog_state(self) -> None:
        """Baut die Symbolsicht einmalig beim Start (noch ohne offenen Plan) und zeigt Ladehinweise an."""
        self._symbol_view_key: tuple | None = None
        self._grid_visible_symbols: set[str] = set()
        self._apply_symbol_view_if_changed()
        if self._controller.symbol_catalog_warning:
            self.status_var.set(self._controller.symbol_catalog_warning)

    @property
    def _documentation_only_symbols(self) -> set[str]:
        """Schlüssel aller Doku-Symbole (eingebaut + eigen), abgeleitet aus der Symbolsicht."""
        return {symbol.key for symbol in self._symbol_view.documentation_symbols}

    def _apply_symbol_view_if_changed(self) -> None:
        """Baut die Symbolsicht und ihre Lookups neu, falls sich eine ihrer Quellen geändert hat.

        Änderungsschlüssel: Identität der Katalog-Tupel aus ``AppState`` (sie werden
        bei jeder programmweiten Änderung ersetzt) und die eigenen Symbole des
        offenen Plans (Wertvergleich, kleine Map). Unverändert → kein Neubau.
        """
        state = self._controller.state
        plan = self.current_plan
        key = (id(state.symbol_catalog), id(state.competence_catalog), dict(plan.custom_symbols) if plan else {})
        if key == self._symbol_view_key:
            return
        catalog_changed = self._symbol_view_key is not None and key[:2] != self._symbol_view_key[:2]
        self._symbol_view_key = key
        view = build_symbol_view(state.symbol_catalog, state.competence_catalog, plan)
        self._derive_symbol_lookups(view)
        if catalog_changed:
            self._on_symbol_catalog_replaced()

    def _derive_symbol_lookups(self, view: SymbolView) -> None:
        """Setzt alle GUI-Lookups aus *view* (einzige Stelle).

        Args:
            view: Frisch gebaute Symbolsicht.
        """
        self._symbol_view = view
        self.symbol_definitions = list(view.catalog)
        self.competences_by_id = dict(view.competences)
        self.symbol_catalog = view.keys
        self.diagnostic_symbol_catalog = view.diagnostic_keys
        self._symbol_by_meaning = view.by_key
        self.effective_documentation_symbols = list(view.documentation_symbols)
        self._effective_symbol_by_key = view.documentation_by_key
        # Dieselbe Referenzmenge wie der Symbolfilter-Dialog: Katalog + eigene Symbole
        # (sonst waeren eigene Symbole selbst im Standardzustand "alles sichtbar" unsichtbar).
        reference = self.symbol_catalog + [s.key for s in view.documentation_symbols if s.is_custom]
        settings = self._controller.state.settings
        self._grid_visible_symbols = visible_grid_symbols(
            reference, settings.grid_hidden_symbols, settings.grid_visible_symbols
        )
        self.pdf_exporter = PdfSeatingPlanExporter(
            self.symbol_definitions, self.competences_by_id, color_palette=self.color_palette
        )

    def _on_symbol_catalog_replaced(self) -> None:
        """Programmweiter Katalog wurde zur Laufzeit ersetzt: Anzeige der Symbole auffrischen."""
        self._build_symbol_shortcuts_bar()
        self._detail_buttons_key = None
        self._legend_lines.clear()
        self._refresh_details_panel()
        self._request_grid_redraw()
        if self.current_plan:
            self._report_custom_shortcut_conflicts()
