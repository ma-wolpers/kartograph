"""JSON-Form der planbezogenen Symbol-Anpassungen (``SeatingPlan.symbol_overrides``).

Additiv im Format v4 (kein Versionssprung)::

    "symbol_overrides": {"Konzentration": {"name": "Fokus", "competences": ["konzentration.arbeiten"]}}

Fehlende Felder bedeuten „Programmstandard“. Lesen ist tolerant: unbrauchbare
Einträge werden übersprungen, umbenannte Altschlüssel über
``canonical_symbol_name`` auf den aktuellen Schlüssel abgebildet.
"""

from __future__ import annotations

from app.core.domain.models_v4 import SymbolOverride
from app.core.domain.symbol_renames import canonical_symbol_name


def serialize_symbol_overrides(overrides: dict[str, SymbolOverride]) -> dict:
    """Schreibt die Anpassungen; nur gesetzte Felder erscheinen.

    Args:
        overrides: Symbolschlüssel → Anpassung.
    """
    result: dict = {}
    for key, override in overrides.items():
        entry: dict = {}
        if override.name is not None:
            entry["name"] = override.name
        if override.competence_ids is not None:
            entry["competences"] = list(override.competence_ids)
        if entry:
            result[key] = entry
    return result


def deserialize_symbol_overrides(raw: object) -> dict[str, SymbolOverride]:
    """Liest die Anpassungen tolerant (fehlend oder kaputt = keine).

    Args:
        raw: Rohwert des Feldes ``symbol_overrides``.
    """
    if not isinstance(raw, dict):
        return {}
    result: dict[str, SymbolOverride] = {}
    for raw_key, entry in raw.items():
        key = canonical_symbol_name(str(raw_key).strip())
        if not key or not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip() or None
        raw_ids = entry.get("competences")
        ids = None
        if isinstance(raw_ids, list):
            ids = tuple(dict.fromkeys(str(cid).strip() for cid in raw_ids if str(cid).strip())) or None
        if name is not None or ids is not None:
            result[key] = SymbolOverride(name=name, competence_ids=ids)
    return result
