"""Regeln für Änderungen am programmweiten Katalog (Symbole und Kompetenzen) — einzige Stelle.

Der Dialog „Symbole und Kompetenzen“ prüft Eingaben mit genau diesen
Funktionen, bevor er dispatcht; die Usecases prüfen noch einmal (ein Fehler, der
bis dorthin durchkommt, ist ein Programmfehler und bleibt sichtbar). Jede
Funktion wirft :class:`CatalogValidationError` mit einem Text für die Statuszeile
des Formulars.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from app.core.domain.custom_symbol_validation import RESERVED_SYMBOL_LETTERS, SPACE_SHORTCUT, normalize_letter
from app.core.domain.models_v4 import CustomSymbolDefinition
from app.core.domain.submission_status import is_required_symbol
from app.core.domain.symbol_catalog import Competence, LevelTexts, SymbolDefinition
from app.core.domain.symbol_glyph_palette import GLYPH_PALETTE


class CatalogValidationError(ValueError):
    """Eine Katalogänderung verletzt eine Regel; ``str(error)`` ist der Hinweis für die Oberfläche."""


def _others(catalog: Sequence[SymbolDefinition], own_key: str | None) -> list[SymbolDefinition]:
    """Alle Katalogsymbole außer dem gerade bearbeiteten.

    Args:
        catalog: Programmweiter Katalog.
        own_key: Schlüssel des bearbeiteten Symbols, ``None`` beim Anlegen.
    """
    return [definition for definition in catalog if definition.key != own_key]


def validate_catalog_shortcut(raw: str, own_key: str | None, catalog: Sequence[SymbolDefinition]) -> str | None:
    """Prüft das Kürzel eines Katalogsymbols; leer = kein Kürzel.

    Erlaubt: leer, ein Buchstabe A–Z (gespeichert klein) oder das unveränderte
    Leertaste-Kürzel eines Symbols, das es schon trägt. Gesperrt: die festen
    Systembuchstaben und Buchstaben anderer Katalogsymbole — auch deaktivierter
    (Deaktivieren gibt ein Kürzel nicht frei; es wird bewusst geleert).

    Args:
        raw: Rohe Eingabe.
        own_key: Schlüssel des bearbeiteten Symbols, ``None`` beim Anlegen.
        catalog: Programmweiter Katalog.
    """
    text = str(raw or "").strip()
    if not text:
        return None
    current = next((d.shortcut for d in catalog if d.key == own_key), None)
    if text.lower() in {SPACE_SHORTCUT, "leertaste"} and current == SPACE_SHORTCUT:
        return SPACE_SHORTCUT
    letter = normalize_letter(text)
    if letter is None:
        raise CatalogValidationError("Als Taste ist nur ein einzelner Buchstabe erlaubt (oder leer lassen).")
    if letter in RESERVED_SYMBOL_LETTERS:
        raise CatalogValidationError(f"{letter} ist fest vergeben (Mitarbeit bzw. Tischsymbol).")
    taken = next((d for d in _others(catalog, own_key) if (d.shortcut or "").upper() == letter), None)
    if taken is not None:
        raise CatalogValidationError(f"{letter} gehört schon zu „{taken.name}“.")
    return letter.lower()


def validate_catalog_name(raw: str, own_key: str | None, catalog: Sequence[SymbolDefinition]) -> str:
    """Prüft den Anzeigenamen: nicht leer und unter den Katalogsymbolen eindeutig (ohne Groß/klein).

    Args:
        raw: Rohe Eingabe.
        own_key: Schlüssel des bearbeiteten Symbols, ``None`` beim Anlegen.
        catalog: Programmweiter Katalog.
    """
    name = " ".join(str(raw or "").split())
    if not name:
        raise CatalogValidationError("Bitte einen Namen eingeben.")
    if any(d.name.lower() == name.lower() for d in _others(catalog, own_key)):
        raise CatalogValidationError(f"„{name}“ heißt schon ein anderes Symbol.")
    return name


def validate_competence_links(ids: Iterable[str], competences: Mapping[str, Competence]) -> tuple[str, ...]:
    """Prüft die Kompetenzen eines Diagnosesymbols: mindestens eine, alle vorhanden.

    Args:
        ids: Gewählte Kompetenz-IDs in Anzeigereihenfolge.
        competences: Kompetenzen nach ID.
    """
    chosen = tuple(dict.fromkeys(ids))
    if not chosen:
        raise CatalogValidationError("Bitte mindestens eine Kompetenz auswählen.")
    unknown = [cid for cid in chosen if cid not in competences]
    if unknown:
        raise CatalogValidationError("Unbekannte Kompetenz: " + ", ".join(unknown))
    return chosen


def validate_new_glyph(codepoint: str, catalog: Sequence[SymbolDefinition]) -> str:
    """Prüft das Zeichen eines neuen Symbols: aus der Palette und noch nicht vergeben.

    Args:
        codepoint: Hex-Codepoint aus ``GLYPH_PALETTE``.
        catalog: Programmweiter Katalog.

    Returns:
        Das Zeichen selbst.
    """
    if codepoint not in {cp for cp, _label in GLYPH_PALETTE}:
        raise CatalogValidationError("Bitte ein Zeichen aus der Auswahl wählen.")
    glyph = chr(int(codepoint, 16))
    if any(d.glyph == glyph for d in catalog):
        raise CatalogValidationError("Dieses Zeichen hat schon ein anderes Symbol.")
    return glyph


def validate_active(definition: SymbolDefinition, active: bool) -> bool:
    """Verhindert das Deaktivieren der Symbole, die „Abgaben zählen“ selbst setzt.

    Args:
        definition: Das bearbeitete Symbol.
        active: Gewünschter Zustand.
    """
    if not active and is_required_symbol(definition):
        raise CatalogValidationError(f"„{definition.name}“ braucht „Abgaben zählen“ – es bleibt aktiv.")
    return active


def validate_competence_fields(
    name: str, group: str, levels: Sequence[str], own_id: str | None, competences: Sequence[Competence]
) -> tuple[str, str, LevelTexts]:
    """Prüft eine Kompetenz: Name und alle drei Stufen nicht leer, Name in der Gruppe eindeutig.

    Args:
        name: Roher Name.
        group: Rohe Gruppe (leer erlaubt).
        levels: Rohe Stufentexte ``(eins, zwei, drei)``.
        own_id: ID der bearbeiteten Kompetenz, ``None`` beim Anlegen.
        competences: Alle Kompetenzen.
    """
    clean_name = " ".join(str(name or "").split())
    clean_group = " ".join(str(group or "").split())
    texts = tuple(" ".join(str(text or "").split()) for text in levels)
    if not clean_name:
        raise CatalogValidationError("Bitte einen Namen für die Kompetenz eingeben.")
    if len(texts) != 3 or not all(texts):
        raise CatalogValidationError("Bitte alle drei Stufen beschreiben.")
    if any(c.id != own_id and c.group == clean_group and c.name.lower() == clean_name.lower() for c in competences):
        raise CatalogValidationError(f"„{clean_name}“ gibt es in dieser Gruppe schon.")
    return clean_name, clean_group, texts  # type: ignore[return-value]


def custom_shortcut_conflicts(shortcut: str | None, custom_symbols: Mapping[str, CustomSymbolDefinition]) -> list[str]:
    """Bedeutungen eigener Plan-Symbole, die ein programmweites Kürzel verdrängen würde (nur Hinweis).

    Args:
        shortcut: Geprüftes Kürzel (klein) oder ``None``.
        custom_symbols: Eigene Symbole des offenen Plans.
    """
    if not shortcut or shortcut == SPACE_SHORTCUT:
        return []
    return [custom.meaning for custom in custom_symbols.values() if (custom.shortcut or "").upper() == shortcut.upper()]
