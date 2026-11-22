"""Zustandsabhängige Regeln der Dokutabelle (reines Python, kein Tk).

Ergänzt die rein strukturelle ``DocColumnAxis`` (``docs_table_model``) um die
Regeln, die UI-Zustand einbeziehen:

- ``SortKey`` / ``SortStack``: die mehrstufige Sortierung als Schlüsselstapel
  (zuletzt angeklickte Spalte zuerst, frühere Klicks als Tie-Breaker).
- ``next_sort_stack``: Sortier-Klickregel (Spaltenkopf).
- ``prune_sort_stack``: vergisst Schlüssel, die keine Gleichstände mehr auflösen.
- ``retain_known_sort_keys``: entfernt Schlüssel verschwundener Spalten.
- ``sort_iids``: Zeilenreihenfolge aus Basisreihenfolge + Schlüsselstapel.
- ``resolve_horizontal_target``: ←/→-Navigation inkl. Datumsanker-Rücksprung.

Warum ein expliziter Stapel: Bis 2026-09-27 sortierte jeder Klick die
*angezeigte* Reihenfolge stabil um, frühere Klicks wirkten so implizit als
Tie-Breaker. Seit das Grid reine Projektion des Modells ist, wird stets ab der
Sitzordnung sortiert -- die implizite Information ging verloren. Der Stapel
macht sie zum Modellzustand, der jeden Tabellen-Neuaufbau übersteht.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from app.adapters.gui.docs_table_model import DocColumnAxis, DocRow


@dataclass(frozen=True)
class SortKey:
    """Eine Sortierstufe: Spalte und Richtung.

    Attributes:
        key: Logischer Spaltenschlüssel (z. B. ``"nachname"``, ``"grade_ab12cd34"``).
        ascending: Aufsteigend sortieren?
    """

    key: str
    ascending: bool = True


SortStack = tuple[SortKey, ...]
"""Sortierstufen, wichtigste (zuletzt angeklickte) zuerst; ``()`` = Sitzordnung."""


def next_sort_stack(stack: SortStack, clicked_key: str) -> SortStack:
    """Sortier-Klickregel: Kopf erneut angeklickt → Richtung umkehren, sonst neue Spalte vorne.

    Eine tiefer im Stapel liegende Spalte wird dabei herausgenommen und
    aufsteigend nach vorne geholt (jede Spalte steht höchstens einmal im
    Stapel). Gekürzt wird hier nicht -- das braucht die Zeilen
    (``prune_sort_stack``).

    Args:
        stack: Bisheriger Stapel.
        clicked_key: Angeklickte Spalte.

    Returns:
        Neuer Stapel.

    Examples:
        ``() → nachname`` ergibt ``(nachname↑,)``; danach ``grade_a`` ergibt
        ``(grade_a↑, nachname↑)``; erneut ``grade_a`` ergibt ``(grade_a↓, nachname↑)``.
    """
    if stack and stack[0].key == clicked_key:
        return (SortKey(clicked_key, not stack[0].ascending), *stack[1:])
    return (SortKey(clicked_key, True), *(entry for entry in stack if entry.key != clicked_key))


def prune_sort_stack(stack: SortStack, rows: Iterable[DocRow], axis: DocColumnAxis) -> SortStack:
    """Kürzt den Stapel hinter dem ersten Präfix, das alle Zeilen eindeutig ordnet.

    Die Zeilen werden Stufe für Stufe nach ihren Sortierwerten gruppiert;
    sobald jede Gruppe nur noch eine Zeile enthält, entscheiden die restlichen
    Stufen nichts mehr und werden vergessen. Bewusst nur beim Klick aufgerufen
    (Wunsch des Nutzers): Was einmal vergessen ist, bleibt vergessen, auch wenn
    später durch Bearbeiten wieder Gleichstände entstehen -- dann entscheidet
    die Sitzordnung. Der Kopf bleibt immer erhalten (Pfeil und Richtung).
    Unbekannte Spalten fallen weg.

    Args:
        stack: Zu kürzender Stapel.
        rows: Alle Tabellenzeilen (Reihenfolge egal).
        axis: Aktuelle Spaltenachse.

    Returns:
        Gekürzter Stapel.
    """
    all_rows = list(rows)
    groups = [all_rows] if len(all_rows) > 1 else []
    kept: list[SortKey] = []
    for entry in stack:
        if not axis.has(entry.key):
            continue
        if kept and not groups:
            break
        kept.append(entry)
        groups = _split_ties(groups, entry.key, axis)
    return tuple(kept)


def _split_ties(groups: list[list[DocRow]], key: str, axis: DocColumnAxis) -> list[list[DocRow]]:
    """Teilt jede Gleichstandsgruppe nach *key* auf und behält nur Gruppen mit mehr als einer Zeile.

    Args:
        groups: Bisher ununterscheidbare Zeilengruppen.
        key: Spalte der nächsten Sortierstufe.
        axis: Spaltenachse (liefert ``sort_value``).

    Returns:
        Weiterhin ununterscheidbare Gruppen.
    """
    remaining: list[list[DocRow]] = []
    for group in groups:
        buckets: dict[tuple, list[DocRow]] = defaultdict(list)
        for row in group:
            buckets[axis.sort_value(row, key)].append(row)
        remaining.extend(bucket for bucket in buckets.values() if len(bucket) > 1)
    return remaining


def retain_known_sort_keys(stack: SortStack, axis: DocColumnAxis) -> SortStack:
    """Entfernt Stufen, deren Spalte es nicht mehr gibt (z. B. gelöschte Notenspalte).

    Die übrigen Stufen bleiben in ihrer Reihenfolge erhalten; ist der Kopf
    betroffen, rückt die nächste Stufe nach.

    Args:
        stack: Bisheriger Stapel.
        axis: Aktuelle Spaltenachse.

    Returns:
        Stapel ohne verschwundene Spalten.
    """
    return tuple(entry for entry in stack if axis.has(entry.key))


def sort_iids(rows: Iterable[DocRow], stack: SortStack, axis: DocColumnAxis) -> list[str]:
    """Berechnet die Zeilenreihenfolge aus Zeilen in Basisreihenfolge und Schlüsselstapel.

    Sortiert stabil nacheinander mit den Stufen in umgekehrter Stapelreihenfolge
    (unwichtigste zuerst) -- Pythons Sortierung ist stabil, auch mit
    ``reverse=True``, also entscheidet jede Stufe nur unter Gleichständen der
    wichtigeren. Letzter Tie-Breaker ist die Basisreihenfolge (Sitzordnung).
    Unbekannte Spalten werden übersprungen.
    Inaktive Zeilen (``DocRow.inactive``, dauerhaft abwesend) stehen danach
    immer ganz unten, in derselben Reihenfolge untereinander -- bewusst als
    eigener Schritt nach dem Sortieren: Ein Flag im Sortierschlüssel würde bei
    absteigender Sortierung mit umgedreht und die Zeilen nach oben holen.

    Args:
        rows: Zeilen in Basisreihenfolge.
        stack: Sortierstufen, wichtigste zuerst.
        axis: Aktuelle Spaltenachse.

    Returns:
        iids in Anzeigereihenfolge.
    """
    ordered = list(rows)
    for entry in reversed(stack):
        if axis.has(entry.key):
            ordered.sort(key=lambda row, key=entry.key: axis.sort_value(row, key), reverse=not entry.ascending)
    return [row.iid for row in ordered if not row.inactive] + [row.iid for row in ordered if row.inactive]


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
