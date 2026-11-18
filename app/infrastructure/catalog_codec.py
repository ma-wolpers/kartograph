"""JSON-Form der Kataloge ``symbols.json`` und ``competences.json`` — einzige Stelle, die sie kennt.

Lesen (``*_from_item``) ist defensiv: unvollständige Einträge ergeben ``None``
und werden vom Loader übersprungen. Schreiben (``*_to_item``) erzeugt die
kanonische Form: Kürzel klein, ``name`` nur wenn er vom ``key`` abweicht,
``role`` nur für Doku-Symbole, ``active`` nur wenn ``False``.

Symbol-Eintrag::

    {"codepoint": "1F3AF", "key": "Konzentration", "name": "…", "shortcut": "z",
     "active": false, "competences": ["konzentration.arbeiten", …]}          # Diagnose
    {"codepoint": "2205", "key": "Abwesend", "shortcut": "space",
     "role": "documentation_only", "legend": {"one": …, "two": …, "three": …}}  # Doku

Kompetenz-Eintrag::

    {"id": "konzentration.arbeiten", "name": "…", "group": "…",
     "levels": {"one": …, "two": …, "three": …}}
"""

from __future__ import annotations

from app.core.domain.custom_symbol_validation import SPACE_SHORTCUT
from app.core.domain.symbol_catalog import Competence, LevelTexts, SymbolDefinition, SymbolRole

_LEVEL_KEYS = ("one", "two", "three")


def parse_codepoint(raw_value: object) -> str | None:
    """Wandelt einen Codepoint-String (z. B. ``"1F4BB"`` oder ``"U+1F4BB"``) in das Zeichen um.

    Args:
        raw_value: Roher Codepoint-Wert; leer oder ungültig ergibt ``None``.
    """
    text = str(raw_value or "").strip().upper()
    if text.startswith("U+"):
        text = text[2:]
    if not text:
        return None
    try:
        return chr(int(text, 16))
    except (TypeError, ValueError, OverflowError):
        return None


def codepoint_key(raw_value: object) -> str | None:
    """Normalisiert einen Codepoint-Wert auf Hex in Großbuchstaben (``"u+2713"`` → ``"2713"``).

    Identität eines eingebauten Symbols im Katalog-Abgleich ist sein Codepoint.

    Args:
        raw_value: Roher Codepoint-Wert.
    """
    glyph = parse_codepoint(raw_value)
    return None if glyph is None else f"{ord(glyph):04X}"


def parse_shortcut(raw_value: object) -> str | None:
    """Validiert ein Ein-Zeichen-Kürzel (klein) oder den Leertaste-Sentinel ``"space"``.

    Args:
        raw_value: Roher Kürzel-Wert; alles andere ergibt ``None``.
    """
    text = str(raw_value or "").strip().lower()
    if text == SPACE_SHORTCUT or len(text) == 1:
        return text
    return None


def _parse_role(raw_value: object) -> SymbolRole:
    """Alles außer ``"documentation_only"`` ist ein Diagnosesymbol.

    Args:
        raw_value: Roher Rollen-Wert.
    """
    return "documentation_only" if str(raw_value or "").strip().lower() == "documentation_only" else "diagnostic"


def _parse_levels(raw_value: object) -> LevelTexts | None:
    """Liest ``{"one", "two", "three"}`` als Tupel; ``None``, wenn eine Stufe fehlt oder leer ist.

    Args:
        raw_value: Rohes Stufen-Objekt.
    """
    if not isinstance(raw_value, dict):
        return None
    texts = tuple(str(raw_value.get(level) or "").strip() for level in _LEVEL_KEYS)
    return texts if all(texts) else None  # type: ignore[return-value]


def _levels_to_item(levels: LevelTexts) -> dict[str, str]:
    """Schreibt Stufentexte in der Reihenfolge der Datendateien (höchste zuerst).

    Args:
        levels: ``(eins, zwei, drei)``.
    """
    return {"three": levels[2], "two": levels[1], "one": levels[0]}


def symbol_from_item(item: object) -> SymbolDefinition | None:
    """Liest einen Symbol-Eintrag; ``None`` bei fehlendem Schlüssel/Codepoint oder fehlenden Doku-Texten.

    Args:
        item: Roh-Eintrag aus ``symbols.json`` (nach der Migration, s. ``symbol_catalog_migration``).
    """
    if not isinstance(item, dict):
        return None
    key = str(item.get("key") or "").strip()
    glyph = parse_codepoint(item.get("codepoint"))
    if not key or glyph is None:
        return None
    role = _parse_role(item.get("role"))
    common = {
        "key": key,
        "name": str(item.get("name") or "").strip() or key,
        "glyph": glyph,
        "shortcut": parse_shortcut(item.get("shortcut")),
        "role": role,
        "active": item.get("active") is not False,
    }
    if role == "documentation_only":
        legend = _parse_levels(item.get("legend"))
        return None if legend is None else SymbolDefinition(**common, frequency_legend=legend)
    raw_ids = item.get("competences")
    ids = tuple(str(cid).strip() for cid in raw_ids if str(cid).strip()) if isinstance(raw_ids, list) else ()
    return SymbolDefinition(**common, competence_ids=tuple(dict.fromkeys(ids)))


def symbol_to_item(definition: SymbolDefinition) -> dict:
    """Schreibt ein Katalogsymbol in die kanonische JSON-Form.

    Args:
        definition: Das zu schreibende Symbol.
    """
    item: dict = {"codepoint": f"{ord(definition.glyph):04X}", "key": definition.key}
    if definition.name != definition.key:
        item["name"] = definition.name
    item["shortcut"] = definition.shortcut
    if not definition.active:
        item["active"] = False
    if definition.role == "documentation_only":
        item["role"] = "documentation_only"
        item["legend"] = _levels_to_item(definition.frequency_legend or ("", "", ""))
    else:
        item["competences"] = list(definition.competence_ids)
    return item


def competence_from_item(item: object) -> Competence | None:
    """Liest einen Kompetenz-Eintrag; ``None`` bei fehlender ID, fehlendem Namen oder Stufentext.

    Args:
        item: Roh-Eintrag aus ``competences.json``.
    """
    if not isinstance(item, dict):
        return None
    competence_id = str(item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    levels = _parse_levels(item.get("levels"))
    if not competence_id or not name or levels is None:
        return None
    return Competence(id=competence_id, name=name, group=str(item.get("group") or "").strip(), levels=levels)


def competence_to_item(competence: Competence) -> dict:
    """Schreibt eine Kompetenz in die kanonische JSON-Form.

    Args:
        competence: Die zu schreibende Kompetenz.
    """
    return {"id": competence.id, "name": competence.name, "group": competence.group,
            "levels": _levels_to_item(competence.levels)}
