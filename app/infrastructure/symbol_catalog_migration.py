"""Feldweise, idempotente Migration alter ``symbols.json``-Arbeitskopien auf Schlüssel + Kompetenzen.

Ältere Arbeitskopien speichern Symbole unter ``meaning`` und Diagnosesymbole mit
eigenen drei Legendentexten. Seit 2026-11-18 gilt ``key`` (+ optional ``name``)
und Diagnosesymbole verknüpfen Kompetenzen (``competences``). Pro Eintrag:

1. Kein ``key``: ``key`` = bisheriges ``meaning`` (so stehen die Symbole in
   Plänen), ``meaning`` entfällt.
2. Diagnosesymbol ohne ``competences``:

   * Legende ist unverändert ein früherer Standardtext
     (:data:`~app.infrastructure.legacy_legend_hashes.LEGACY_LEGEND_SHA256`)
     → die Standard-Verknüpfungen des Symbols;
   * Legende wurde selbst geändert, oder das Symbol ist kein eingebautes
     → eine lokale Kompetenz ``local.<slug>`` mit genau diesen Texten (nichts geht
     verloren; existiert sie schon, wird sie wiederverwendet);
   * keine Legende → Standard-Verknüpfungen, sonst leer.

   Danach entfällt ``legend``. Ein explizites ``competences: []`` ist eine eigene
   Entscheidung und wird nie neu befüllt.

Ein zweiter Lauf ändert nichts mehr; ein Abbruch zwischen dem Schreiben von
``competences.json`` und ``symbols.json`` ist harmlos, weil die lokale
Kompetenz-ID deterministisch ist.
"""

from __future__ import annotations

from app.core.domain.symbol_catalog import slugify
from app.infrastructure.catalog_codec import codepoint_key
from app.infrastructure.legacy_legend_hashes import LEGACY_LEGEND_SHA256, legend_fingerprint

LOCAL_COMPETENCE_PREFIX = "local."
LOCAL_COMPETENCE_GROUP = "Eigene"


def local_competence_id(key: str) -> str:
    """Deterministische ID der lokalen Kompetenz für das Symbol *key* (z. B. ``local.umgang_mit_material``).

    Args:
        key: Symbolschlüssel.
    """
    return LOCAL_COMPETENCE_PREFIX + slugify(key)


def migrate_symbol_items(items: list, default_items: list, competences: list) -> tuple[bool, bool, list[str]]:
    """Migriert alle Symbol-Einträge in *items* an Ort und Stelle.

    Args:
        items: Einträge der Symbol-Arbeitskopie (werden verändert).
        default_items: Einträge der Standard-Symboldatei (für Standard-Verknüpfungen).
        competences: Einträge der Kompetenz-Arbeitskopie (lokale Kompetenzen werden angehängt).

    Returns:
        ``(Symbole geändert, Kompetenzen geändert, Namen übernommener eigener Legenden)``.
    """
    defaults = {codepoint_key(item.get("codepoint")): item for item in default_items if isinstance(item, dict)}
    symbols_changed = competences_changed = False
    adopted: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if "key" not in item and "meaning" in item:
            item["key"] = item.pop("meaning")
            symbols_changed = True
        if item.get("role") == "documentation_only" or "competences" in item:
            continue
        default = defaults.get(codepoint_key(item.get("codepoint")))
        linked, created = _links_for(item, default, competences)
        item["competences"] = linked
        item.pop("legend", None)
        symbols_changed = True
        if created is not None:
            competences.append(created)
            competences_changed = True
        if linked and linked[0].startswith(LOCAL_COMPETENCE_PREFIX):
            adopted.append(str(item.get("key") or ""))
    return symbols_changed, competences_changed, adopted


def _links_for(item: dict, default: dict | None, competences: list) -> tuple[list[str], dict | None]:
    """Bestimmt die Verknüpfungen für ein altes Diagnosesymbol und ggf. eine neue lokale Kompetenz.

    Args:
        item: Alter Symbol-Eintrag (mit ``key``).
        default: Standardeintrag mit gleichem Codepoint, falls eingebaut.
        competences: Vorhandene Kompetenz-Einträge (nur gelesen).

    Returns:
        ``(Kompetenz-IDs, neu anzulegender Kompetenz-Eintrag oder None)``.
    """
    default_links = list(default.get("competences") or []) if default else []
    legend = item.get("legend")
    if not isinstance(legend, dict):
        return default_links, None
    texts = tuple(str(legend.get(level) or "").strip() for level in ("one", "two", "three"))
    cp = codepoint_key(item.get("codepoint"))
    if default and legend_fingerprint(*texts) in LEGACY_LEGEND_SHA256.get(cp or "", frozenset()):
        return default_links, None
    if not all(texts):
        return default_links, None
    key = str(item.get("key") or "").strip()
    competence_id = local_competence_id(key)
    if any(isinstance(c, dict) and c.get("id") == competence_id for c in competences):
        return [competence_id], None
    created = {"id": competence_id, "name": key, "group": LOCAL_COMPETENCE_GROUP,
               "levels": {"three": texts[2], "two": texts[1], "one": texts[0]}}
    return [competence_id], created
