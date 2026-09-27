"""Umbenennungen eingebauter Symbole (Bedeutungstext = Speicherschlüssel).

Eingebaute Symbole werden in Plänen (Diagnoseprofil, Doku-Einträge) und in
den Einstellungen (``grid_visible_symbols``) unter ihrem Bedeutungstext aus
``config/symbols.json`` gespeichert. Wird eine Bedeutung umbenannt, bildet
diese Tabelle den alten Schlüssel beim Laden auf den neuen ab, damit bereits
erfasste Einträge erhalten bleiben. Beim nächsten Speichern steht dann nur
noch der neue Schlüssel in der Datei.
"""

from __future__ import annotations

LEGACY_SYMBOL_RENAMES: dict[str, str] = {
    "Mathem. Fachkompetenz": "Fachkompetenz",
}


def canonical_symbol_name(name: str) -> str:
    """Liefert den aktuellen Speicherschlüssel für einen (ggf. alten) Symbolnamen.

    Args:
        name: Gespeicherter Symbolname (Bedeutungstext oder ID eines eigenen Symbols).

    Returns:
        Der umbenannte Schlüssel, falls *name* ein alter Name ist, sonst *name* unverändert.
    """
    return LEGACY_SYMBOL_RENAMES.get(name, name)


def merge_symbol_strength(symbols: dict[str, int], name: str, strength: int) -> None:
    """Trägt *strength* unter dem kanonischen Namen von *name* in *symbols* ein.

    Stehen alter und neuer Schlüssel gleichzeitig in einer Datei, gewinnt die
    höhere Stärke — so geht beim Zusammenführen keine Beobachtung verloren.

    Args:
        symbols: Ziel-Dict (Symbolname → Stärke), wird verändert.
        name: Gespeicherter Symbolname (alt oder neu).
        strength: Bereits validierte Stärke.
    """
    key = canonical_symbol_name(name)
    symbols[key] = max(symbols.get(key, 0), strength)
