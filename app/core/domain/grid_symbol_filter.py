"""Welche Symbole das Sitzraster zeigt — einzige Regel für Dialog und Darstellung.

Gespeichert wird seit 2026-11-18, was **ausgeblendet** ist
(``KartographSettings.grid_hidden_symbols``), nicht mehr, was sichtbar ist:
Mit einer Sichtbar-Liste blieben alle später hinzukommenden Symbole (neue
eingebaute oder eigene) unsichtbar, sobald der Filter einmal gespeichert war.

Ältere Einstellungen kennen nur ``grid_visible_symbols``. Sie gelten weiter,
bis der Filter das nächste Mal gespeichert wird (GRENZE: bis dahin bleiben neue
Symbole bei einer solchen Alt-Einstellung ausgeblendet).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def visible_grid_symbols(
    reference: Sequence[str],
    hidden: Sequence[str] | None,
    legacy_visible: Sequence[str] = (),
) -> set[str]:
    """Gibt die Schlüssel zurück, die das Raster anzeigt.

    Args:
        reference: Alle wählbaren Schlüssel (Katalog + eigene Symbole des Plans).
        hidden: Gespeicherte Ausblendliste; ``None`` = noch nie im neuen Format gespeichert.
        legacy_visible: Alte Sichtbar-Liste (nur ausgewertet, wenn *hidden* ``None`` ist).
    """
    if hidden is not None:
        return set(reference) - set(hidden)
    legacy = set(legacy_visible) & set(reference)
    return legacy or set(reference)


def hidden_from_selection(reference: Sequence[str], selected: Iterable[str]) -> tuple[str, ...]:
    """Wandelt die im Dialog angehakten Schlüssel in die zu speichernde Ausblendliste um.

    Nichts angehakt bedeutet „alle anzeigen“ (ein leeres Raster wäre nie gewollt).

    Args:
        reference: Alle im Dialog angebotenen Schlüssel in Anzeigereihenfolge.
        selected: Die angehakten Schlüssel.
    """
    chosen = set(selected)
    if not chosen:
        return ()
    return tuple(key for key in reference if key not in chosen)
