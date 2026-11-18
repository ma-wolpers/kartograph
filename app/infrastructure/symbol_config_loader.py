"""Lädt den programmweiten Katalog — Symbole und Kompetenzen — aus den lokalen Arbeitskopien.

Einziger Einstieg: :func:`load_catalog`. Ablauf:

1. beide Arbeitskopien laden, reparieren und um neue Standardeinträge ergänzen
   (gemeinsame Regel in ``catalog_working_copy.py``);
2. alte Symbol-Einträge migrieren (``symbol_catalog_migration.py``);
3. geänderte Dateien schreiben — Kompetenzen zuerst, weil migrierte Symbole auf
   neu angelegte lokale Kompetenzen verweisen können;
4. beide Listen über ``catalog_codec.py`` (einzige Stelle des JSON-Formats) parsen.

Formulierungsregeln für Kompetenzen und die Checkliste für neue Symbole:
``docs/SYMBOLE.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from app.core.domain.symbol_catalog import Competence, SymbolDefinition
from app.infrastructure.catalog_codec import codepoint_key, competence_from_item, parse_shortcut, symbol_from_item
from app.infrastructure.catalog_working_copy import (
    WorkingCopy,
    WorkingCopySpec,
    load_working_copy,
    read_default_items,
    reset_working_copy,
    write_working_copy,
)
from app.infrastructure.symbol_catalog_migration import migrate_symbol_items

DEFAULT_SYMBOLS_PATH = Path(__file__).with_name("default_symbols.json")
"""Einzige Quelle der eingebauten Symbole (reine Datendatei, versioniert)."""

DEFAULT_COMPETENCES_PATH = Path(__file__).with_name("default_competences.json")
"""Einzige Quelle der eingebauten Kompetenzen und ihrer Stufentexte (reine Datendatei, versioniert)."""

_T = TypeVar("_T")


def _admit_new_symbol(item: dict, items: list) -> str | None:
    """Lässt das Kürzel eines neuen Standardsymbols weg, wenn die Arbeitskopie es schon vergibt.

    Args:
        item: Neuer Standardeintrag (wird verändert).
        items: Vorhandene Einträge der Arbeitskopie.

    Returns:
        Hinweistext bei einem Konflikt, sonst ``None``.
    """
    shortcut = parse_shortcut(item.get("shortcut"))
    used = {parse_shortcut(other.get("shortcut")) for other in items if isinstance(other, dict)} - {None}
    if shortcut is None or shortcut not in used:
        return None
    item["shortcut"] = None
    return f"„{item.get('key')}“ ohne Kürzel ergänzt ({shortcut.upper()} ist schon vergeben)"


SYMBOL_SPEC = WorkingCopySpec(
    label="Symbol-Konfiguration",
    list_key="symbols",
    known_key="known_builtin_codepoints",
    default_path=DEFAULT_SYMBOLS_PATH,
    identity=lambda item: codepoint_key(item.get("codepoint")),
    admit_new=_admit_new_symbol,
)

COMPETENCE_SPEC = WorkingCopySpec(
    label="Kompetenz-Konfiguration",
    list_key="competences",
    known_key="known_builtin_competence_ids",
    default_path=DEFAULT_COMPETENCES_PATH,
    identity=lambda item: str(item.get("id") or "").strip() or None,
)


@dataclass(frozen=True)
class CatalogLoadResult:
    """Ergebnis von :func:`load_catalog`.

    Attributes:
        symbols: Gültige Katalogsymbole in Dateireihenfolge.
        competences: Gültige Kompetenzen in Dateireihenfolge.
        warning: Hinweise für die Statuszeile, sonst ``None``.
    """

    symbols: tuple[SymbolDefinition, ...]
    competences: tuple[Competence, ...]
    warning: str | None


def load_catalog(symbols_path: Path, competences_path: Path) -> CatalogLoadResult:
    """Lädt, repariert, ergänzt und migriert beide Arbeitskopien und parst sie.

    Enthält eine Datei nach dem Parsen keinen einzigen gültigen Eintrag, wird sie
    aus der Standarddatei neu geschrieben — die Anwendung startet nie ganz ohne
    Symbole oder Kompetenzen.

    Args:
        symbols_path: Arbeitskopie ``config/symbols.json``.
        competences_path: Arbeitskopie ``config/competences.json``.

    Raises:
        ValueError: Ein Pfad ist die versionierte Standarddatei.
    """
    competence_copy = load_working_copy(competences_path, COMPETENCE_SPEC)
    symbol_copy = load_working_copy(symbols_path, SYMBOL_SPEC)
    symbols_migrated, competences_added, adopted = migrate_symbol_items(
        symbol_copy.items(SYMBOL_SPEC), read_default_items(SYMBOL_SPEC), competence_copy.items(COMPETENCE_SPEC)
    )
    warnings = competence_copy.warnings + symbol_copy.warnings
    if adopted:
        warnings.append("Eigene Legendentexte als Kompetenz übernommen: " + ", ".join(adopted))
    if competence_copy.dirty or competences_added:
        write_working_copy(competences_path, competence_copy.payload, COMPETENCE_SPEC)
    if symbol_copy.dirty or symbols_migrated:
        write_working_copy(symbols_path, symbol_copy.payload, SYMBOL_SPEC)
    competences = _parse_or_reset(competences_path, competence_copy, COMPETENCE_SPEC, competence_from_item, warnings)
    symbols = _parse_or_reset(symbols_path, symbol_copy, SYMBOL_SPEC, symbol_from_item, warnings)
    return CatalogLoadResult(symbols, competences, "\n".join(warnings) or None)


def _parse_or_reset(
    path: Path,
    copy: WorkingCopy,
    spec: WorkingCopySpec,
    parse: Callable[[object], _T | None],
    warnings: list[str],
) -> tuple[_T, ...]:
    """Parst die Einträge von *copy*; ohne gültigen Eintrag Rückfall auf die Standards.

    Args:
        path: Arbeitskopie (wird beim Rückfall neu geschrieben).
        copy: Geladene Arbeitskopie.
        spec: Katalogbeschreibung.
        parse: Codec-Funktion für einen Eintrag.
        warnings: Hinweisliste (wird beim Rückfall ergänzt).
    """
    parsed = tuple(entry for item in copy.items(spec) if (entry := parse(item)) is not None)
    if parsed:
        return parsed
    payload = reset_working_copy(path, spec)
    warnings.append(f"{spec.label} ohne gültige Einträge; Standardwerte wurden nach {path} geschrieben.")
    return tuple(entry for item in payload[spec.list_key] if (entry := parse(item)) is not None)
