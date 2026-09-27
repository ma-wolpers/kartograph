"""Zustandsabhängige Regeln der Dokutabelle (reines Python, kein Tk).

Ergänzt die rein strukturelle ``DocColumnAxis`` (``docs_table_model``) um die
Regeln, die UI-Zustand einbeziehen:

- ``sort_iids``: Zeilenreihenfolge aus Basisreihenfolge + Sortierspezifikation.
- ``next_sort_spec``: Sortier-Klickregel (Spaltenkopf).
- ``resolve_horizontal_target``: ←/→-Navigation inkl. Datumsanker-Rücksprung.
"""

from __future__ import annotations

from typing import Iterable

from app.adapters.gui.docs_table_model import DocColumnAxis, DocRow


def sort_iids(rows: Iterable[DocRow], key: str | None, ascending: bool, axis: DocColumnAxis) -> list[str]:
    """Berechnet die Zeilenreihenfolge aus Zeilen in Basisreihenfolge und Sortierspezifikation.

    Stabil: gleiche Sortierwerte behalten die Basisreihenfolge (Sitzordnung).
    Ohne (gültige) Sortierspalte bleibt die Basisreihenfolge unverändert.

    Args:
        rows: Zeilen in Basisreihenfolge.
        key: Sortierspalte oder ``None``.
        ascending: Aufsteigend sortieren?
        axis: Aktuelle Spaltenachse.

    Returns:
        iids in Anzeigereihenfolge.
    """
    ordered = list(rows)
    if key is None or not axis.has(key):
        return [row.iid for row in ordered]
    ordered.sort(key=lambda row: axis.sort_value(row, key), reverse=not ascending)
    return [row.iid for row in ordered]


def next_sort_spec(current_key: str | None, current_ascending: bool, clicked_key: str) -> tuple[str, bool]:
    """Sortier-Klickregel: gleiche Spalte kehrt die Richtung um, neue Spalte startet aufsteigend.

    Args:
        current_key: Bisherige Sortierspalte oder ``None``.
        current_ascending: Bisherige Richtung.
        clicked_key: Angeklickte Spalte.

    Returns:
        Neue ``(sort_key, ascending)``-Spezifikation.
    """
    if current_key == clicked_key:
        return clicked_key, not current_ascending
    return clicked_key, True


def resolve_horizontal_target(
    axis: DocColumnAxis, active_key: str | None, date_anchor_index: int, delta: int
) -> str | None:
    """Bestimmt die Zielspalte für ←/→ (reine Entscheidung, ohne Tk).

    Einzige zustandsabhängige Sonderregel: von der ersten auswählbaren
    RIGHT-Spalte führt ← zurück zum *aktuellen Datumsanker* (nicht zum letzten
    Datum). Alle übrigen Übergänge kommen rein strukturell aus der Achse.

    Args:
        axis: Aktuelle Spaltenachse.
        active_key: Aktuell aktive Spalte.
        date_anchor_index: Aktueller Datumsanker (Index).
        delta: ``1`` (rechts) oder ``-1`` (links).

    Returns:
        Zielspalte oder ``None`` am Rand.
    """
    if delta < 0 and active_key is not None and active_key == axis.first_selectable_nondate_right():
        anchor_key = axis.date_key(date_anchor_index)
        if anchor_key is not None:
            return anchor_key
    return axis.neighbor(active_key, delta)
