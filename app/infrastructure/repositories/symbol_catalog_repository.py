"""JSON-Repository des programmweiten Katalogs (``config/symbols.json`` + ``config/competences.json``).

Laden über den einen Einstieg ``symbol_config_loader.load_catalog``; Speichern
schreibt beide Arbeitskopien in der kanonischen Form von ``catalog_codec`` und
behält die Listen bekannter Standardeinträge bei (sonst kämen bewusst
gelöschte Standards beim nächsten Start zurück). Kompetenzen werden zuerst
geschrieben, weil Symbole auf sie verweisen.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from app.core.domain.symbol_catalog import CatalogContents, Competence, SymbolDefinition
from app.infrastructure.catalog_codec import competence_to_item, symbol_to_item
from app.infrastructure.catalog_working_copy import WorkingCopySpec, write_working_copy
from app.infrastructure.symbol_config_loader import COMPETENCE_SPEC, SYMBOL_SPEC, load_catalog


class JsonSymbolCatalogRepository:
    """Liest und schreibt den programmweiten Katalog (implementiert ``SymbolCatalogRepository``)."""

    def __init__(self, symbols_path: Path, competences_path: Path) -> None:
        """Merkt sich die beiden Arbeitskopien.

        Args:
            symbols_path: ``config/symbols.json``.
            competences_path: ``config/competences.json``.
        """
        self.symbols_path = symbols_path
        self.competences_path = competences_path

    def load(self) -> CatalogContents:
        """Lädt (repariert, ergänzt, migriert) beide Arbeitskopien."""
        return load_catalog(self.symbols_path, self.competences_path)

    def save(self, symbols: Sequence[SymbolDefinition], competences: Sequence[Competence]) -> None:
        """Schreibt beide Arbeitskopien atomar, Kompetenzen zuerst.

        Args:
            symbols: Vollständiger Symbolkatalog.
            competences: Vollständige Kompetenzliste.
        """
        self._write(self.competences_path, COMPETENCE_SPEC, [competence_to_item(c) for c in competences])
        self._write(self.symbols_path, SYMBOL_SPEC, [symbol_to_item(s) for s in symbols])

    @staticmethod
    def _write(path: Path, spec: WorkingCopySpec, items: list[dict]) -> None:
        """Ersetzt die Einträge von *path*, die Liste bekannter Standards bleibt erhalten.

        Args:
            path: Arbeitskopie.
            spec: Katalogbeschreibung.
            items: Neue Einträge in kanonischer Form.
        """
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
        known = previous.get(spec.known_key, []) if isinstance(previous, dict) else []
        write_working_copy(path, {spec.list_key: items, spec.known_key: known}, spec)
