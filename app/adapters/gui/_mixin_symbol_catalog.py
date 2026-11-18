"""Symbolkatalog-Zustand des Kartograph-Hauptfensters (eingebaute Symbole + Kompetenzen).

Einzige Stelle, an der die GUI ihre Katalog-Lookups aus ``AppState``
ableitet (Schlüssel-Listen, Symbol nach Schlüssel, Kürzel → Symbol,
Kompetenz nach ID) und den PDF-Exporter mit dem Katalog versorgt.
``AppState.symbol_catalog``/``competence_catalog`` sind beim Controller-Start
bereits geladen — die GUI liest nur daraus und öffnet keine Konfigurationsdatei.
"""

from __future__ import annotations

from app.core.domain.effective_symbol import EffectiveSymbol
from app.core.domain.models_v4 import CustomSymbolDefinition
from app.core.domain.symbol_catalog import Competence
from app.infrastructure.exporters.pdf_exporter import PdfSeatingPlanExporter


class SymbolCatalogMixin:
    """Mixin: baut die Katalog-Lookups des Hauptfensters einmalig beim Start auf."""

    def _init_symbol_catalog_state(self) -> None:
        """Leitet alle Katalog-Lookups aus dem geladenen ``AppState`` ab und zeigt Ladehinweise an.

        Setzt ``symbol_definitions``, ``symbol_catalog`` (Schlüssel in
        Katalogreihenfolge), ``diagnostic_symbol_catalog``, ``_symbol_by_meaning``
        (Schlüssel → Definition), ``_shortcut_to_symbol``, ``competences_by_id``,
        die Doku-Symbol-Projektion und den PDF-Exporter.
        """
        state = self._controller.state
        self.symbol_definitions = list(state.symbol_catalog)
        self.competences_by_id: dict[str, Competence] = {item.id: item for item in state.competence_catalog}
        self.symbol_catalog = [item.key for item in self.symbol_definitions]
        self.diagnostic_symbol_catalog = [item.key for item in self.symbol_definitions if item.role == "diagnostic"]
        self._symbol_by_meaning = {item.key: item for item in self.symbol_definitions}
        self._shortcut_to_symbol = self._build_symbol_shortcut_map(self.symbol_definitions)
        self.effective_documentation_symbols: list[EffectiveSymbol] = []
        self._effective_symbol_by_key: dict[str, EffectiveSymbol] = {}
        # None (nicht {}) als "noch nie berechnet"-Sentinel -- sonst wuerde der
        # Aenderungs-Waechter den allerersten Aufruf mit {} faelschlich als
        # "unveraendert" ueberspringen.
        self._last_custom_symbols_snapshot: dict[str, CustomSymbolDefinition] | None = None
        self._grid_visible_symbols: set[str] = set()
        self._rebuild_effective_documentation_symbols_if_changed({})
        self.pdf_exporter = PdfSeatingPlanExporter(
            self.symbol_definitions, self.competences_by_id, color_palette=self.color_palette
        )
        if self._controller.symbol_catalog_warning:
            self.status_var.set(self._controller.symbol_catalog_warning)
