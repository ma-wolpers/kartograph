"""Logisches Tabellenmodell der Dokuansicht (reines Python, kein Tk).

Die Dokuansicht ist fachlich **eine logische Tabelle**, die in drei
synchronisierte Treeviews projiziert wird (``DocsPane.NAMES`` / ``MAIN`` /
``RIGHT``). Dieses Modul hält die Struktur dieser Tabelle, unabhängig von
jedem Widget:

- ``DocRow``: eine Tabellenzeile (Anzeige-Strings) je Schüler.
- ``DocColumnAxis``: die eine logische horizontale Spaltenachse
  ``nachname → vorname → date_0 … date_n → summary → grade_* → totals → overall``
  inkl. Pane-Zuordnung, Nachbarschaft und Sortierwerten. Rein strukturell —
  kennt keinen UI-Zustand (keinen Datumsanker, keine Auswahl, keinen Fokus).

Zustandsabhängige Regeln (Sortierung, Sortier-Klickregel, ←/→-Navigation mit
Datumsanker) liegen getrennt davon in ``docs_table_rules``.

Grenze der Positionsrepräsentation: ``DocRow.date_cells`` und
``DocRow.fixed_cells`` sind intern positionsbasierte Tupel. **Nur**
``DocColumnAxis.value_of`` / ``DocColumnAxis.sort_value`` und die
``DocRow.*_projection``-Methoden dürfen einen Tupelindex einer Spalte zuordnen;
alles außerhalb dieses Moduls arbeitet ausschließlich mit Spaltenschlüsseln.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Sequence

NACHNAME_KEY = "nachname"
VORNAME_KEY = "vorname"
SUMMARY_KEY = "summary"

_ColumnKind = Literal["name", "date", "summary", "grade", "total"]


class DocsPane(Enum):
    """Die drei visuellen Projektionen (Treeviews) der Dokutabelle."""

    NAMES = "names"
    MAIN = "main"
    RIGHT = "right"


@dataclass(frozen=True)
class DocRow:
    """Eine logische Zeile der Dokutabelle (reine Anzeige-Strings).

    Attributes:
        iid: Zeilen-ID, in allen drei Treeviews identisch (Schüler-ID als String).
        nachname: Angezeigter Nachname (inkl. Fallback ``"(x,y)"`` bei leerem Nachnamen).
        vorname: Angezeigter Vorname.
        date_cells: Zelltexte der Datumsspalten, in Achsenreihenfolge.
        fixed_cells: Zelltexte der festen Spalten (Zusammenfassung, Noten,
            Zwischensummen, Gesamtnote), in Achsenreihenfolge.
    """

    iid: str
    nachname: str
    vorname: str
    date_cells: tuple[str, ...]
    fixed_cells: tuple[str, ...]

    def names_projection(self) -> tuple[str, list[str]]:
        """Liefert ``(text, values)`` für das NAMES-Pane (``#0`` = Nachname, ``vorname``).

        Returns:
            Tupel aus Baumspalten-Text und Werteliste für ``Treeview.insert``/``item``.
        """
        return self.nachname, [self.vorname]

    def main_projection(self) -> list[str]:
        """Liefert die Werteliste für das MAIN-Pane (nur Datumsspalten).

        Returns:
            Zelltexte in der Reihenfolge der MAIN-Treeview-Spalten.
        """
        return list(self.date_cells)

    def right_projection(self) -> list[str]:
        """Liefert die Werteliste für das RIGHT-Pane (feste Spalten).

        Returns:
            Zelltexte in der Reihenfolge der RIGHT-Treeview-Spalten.
        """
        return list(self.fixed_cells)


@dataclass(frozen=True)
class DocColumn:
    """Eine logische Spalte der Dokutabelle.

    Attributes:
        key: Spaltenschlüssel (``"nachname"``, ``"date_3"``, ``"grade_x"``, …).
        pane: Pane, in dem die Spalte dargestellt wird.
        kind: Spaltenart; wird ausschließlich innerhalb dieses Moduls ausgewertet.
    """

    key: str
    pane: DocsPane
    kind: _ColumnKind


def _fixed_column_kind(key: str) -> _ColumnKind:
    """Ordnet einer festen Spalten-ID ihre Spaltenart zu.

    Args:
        key: Feste Spalten-ID (``"summary"``, ``"grade_*"``, ``"written_total"``, …).

    Returns:
        ``"summary"``, ``"grade"`` oder ``"total"`` (Zwischensummen und Gesamtnote).
    """
    if key == SUMMARY_KEY:
        return "summary"
    if key.startswith("grade_"):
        return "grade"
    return "total"


class DocColumnAxis:
    """Die logische horizontale Spaltenachse über alle drei Panes (zustandsfrei).

    Reihenfolge: ``nachname, vorname`` (NAMES) → Datumsspalten (MAIN) →
    feste Spalten (RIGHT). Enthält nur Struktur; zustandsabhängige Regeln
    (Datumsanker-Rücksprung) liegen in ``resolve_horizontal_target``.
    """

    def __init__(self, date_column_ids: Sequence[str], fixed_column_ids: Sequence[str]) -> None:
        """Baut die Achse aus den aktuellen Datums- und festen Spalten-IDs.

        Args:
            date_column_ids: IDs der Datumsspalten (``date_0`` …) in Anzeigereihenfolge.
            fixed_column_ids: IDs der festen Spalten in Anzeigereihenfolge.
        """
        columns: list[DocColumn] = [
            DocColumn(NACHNAME_KEY, DocsPane.NAMES, "name"),
            DocColumn(VORNAME_KEY, DocsPane.NAMES, "name"),
        ]
        columns.extend(DocColumn(key, DocsPane.MAIN, "date") for key in date_column_ids)
        columns.extend(DocColumn(key, DocsPane.RIGHT, _fixed_column_kind(key)) for key in fixed_column_ids)
        self._columns: tuple[DocColumn, ...] = tuple(columns)
        self._position_by_key = {column.key: pos for pos, column in enumerate(self._columns)}
        self._date_ids: tuple[str, ...] = tuple(date_column_ids)
        self._fixed_ids: tuple[str, ...] = tuple(fixed_column_ids)
        self._date_index = {key: idx for idx, key in enumerate(self._date_ids)}
        self._fixed_index = {key: idx for idx, key in enumerate(self._fixed_ids)}

    @property
    def keys(self) -> tuple[str, ...]:
        """Alle Spaltenschlüssel in Achsenreihenfolge."""
        return tuple(column.key for column in self._columns)

    def has(self, key: str | None) -> bool:
        """Prüft, ob *key* eine Spalte dieser Achse ist.

        Args:
            key: Spaltenschlüssel oder ``None``.

        Returns:
            ``True``, falls die Spalte existiert.
        """
        return key is not None and key in self._position_by_key

    def _column(self, key: str) -> DocColumn:
        """Liefert die Spalte zu *key* (Aufrufer hat ``has`` geprüft).

        Args:
            key: Existierender Spaltenschlüssel.

        Returns:
            Die zugehörige ``DocColumn``.
        """
        return self._columns[self._position_by_key[key]]

    def pane_of(self, key: str) -> DocsPane:
        """Liefert das Pane, in dem *key* dargestellt wird.

        Args:
            key: Existierender Spaltenschlüssel.

        Returns:
            Das zuständige ``DocsPane``.
        """
        return self._column(key).pane

    def pane_columns(self, pane: DocsPane) -> tuple[str, ...]:
        """Liefert die ``columns``-Konfiguration des Treeviews für *pane*.

        Die Baumspalte ``#0`` (Nachname) gehört nicht zu ``columns``.

        Args:
            pane: Ziel-Pane.

        Returns:
            Spaltenschlüssel in Treeview-Reihenfolge.
        """
        if pane is DocsPane.NAMES:
            return (VORNAME_KEY,)
        if pane is DocsPane.MAIN:
            return self._date_ids
        return self._fixed_ids

    def tree_column(self, key: str) -> str:
        """Übersetzt einen Spaltenschlüssel in die Treeview-Spaltenkennung.

        Einzige Stelle, die die Baumspalte ``#0`` kennt.

        Args:
            key: Existierender Spaltenschlüssel.

        Returns:
            ``"#0"`` für den Nachnamen, sonst der Schlüssel selbst.
        """
        return "#0" if key == NACHNAME_KEY else key

    def is_selectable(self, key: str | None) -> bool:
        """Prüft, ob *key* per Klick/Navigation aktive Spalte werden darf.

        Die Zusammenfassung ist nur sortierbar, nicht auswählbar.

        Args:
            key: Spaltenschlüssel oder ``None``.

        Returns:
            ``True`` für existierende, auswählbare Spalten.
        """
        return self.has(key) and self._column(key).kind != "summary"

    def is_date(self, key: str | None) -> bool:
        """Prüft, ob *key* eine Datumsspalte ist.

        Args:
            key: Spaltenschlüssel oder ``None``.

        Returns:
            ``True`` für Datumsspalten.
        """
        return key is not None and key in self._date_index

    def is_grade(self, key: str | None) -> bool:
        """Prüft, ob *key* eine editierbare Notenspalte (``grade_*``) ist.

        Args:
            key: Spaltenschlüssel oder ``None``.

        Returns:
            ``True`` für Notenspalten.
        """
        return self.has(key) and self._column(key).kind == "grade"

    def date_key(self, index: int) -> str | None:
        """Liefert den Schlüssel der Datumsspalte mit Index *index* (geklemmt).

        Args:
            index: Datumsindex (wird in den gültigen Bereich geklemmt).

        Returns:
            Datumsspalten-Schlüssel oder ``None``, falls es keine Datumsspalten gibt.
        """
        if not self._date_ids:
            return None
        return self._date_ids[max(0, min(index, len(self._date_ids) - 1))]

    def date_index_of(self, key: str) -> int | None:
        """Liefert den Datumsindex einer Datumsspalte.

        Args:
            key: Spaltenschlüssel.

        Returns:
            Index in der Datumsachse oder ``None``, falls *key* keine Datumsspalte ist.
        """
        return self._date_index.get(key)

    def first_selectable_nondate_right(self) -> str | None:
        """Liefert die erste auswählbare Spalte im RIGHT-Pane (überspringt ``summary``).

        Returns:
            Spaltenschlüssel oder ``None``, falls keine existiert.
        """
        for key in self._fixed_ids:
            if self.is_selectable(key):
                return key
        return None

    def neighbor(self, key: str | None, step: int) -> str | None:
        """Liefert die strukturell benachbarte auswählbare Spalte.

        Kennt keinen Datumsanker — ``date_i`` hat immer ``date_i±1`` bzw. die
        Pane-Grenze als Nachbarn.

        Args:
            key: Ausgangsspalte.
            step: ``1`` (rechts) oder ``-1`` (links).

        Returns:
            Nachbarschlüssel oder ``None`` am Rand bzw. bei unbekanntem *key*.
        """
        if step not in (-1, 1) or not self.has(key):
            return None
        position = self._position_by_key[key] + step
        while 0 <= position < len(self._columns):
            candidate = self._columns[position].key
            if self.is_selectable(candidate):
                return candidate
            position += step
        return None

    def resolve_clicked(self, pane: DocsPane, identify_result: str, tree_columns: Sequence[str]) -> str | None:
        """Übersetzt ``Treeview.identify_column()`` in einen Spaltenschlüssel.

        ``"#N"`` wird über das Widget-eigene ``columns``-Tupel aufgelöst statt
        über einen hart codierten Offset; ``"#0"`` ist nur im NAMES-Pane der
        Nachname.

        Args:
            pane: Pane, in dem geklickt wurde.
            identify_result: Rückgabe von ``identify_column`` (``"#0"``, ``"#1"``, … oder ``""``).
            tree_columns: ``columns``-Tupel des geklickten Treeviews.

        Returns:
            Spaltenschlüssel oder ``None`` bei Klick außerhalb einer Spalte.
        """
        if not identify_result.startswith("#"):
            return None
        try:
            raw_index = int(identify_result[1:])
        except ValueError:
            return None
        if raw_index == 0:
            return NACHNAME_KEY if pane is DocsPane.NAMES else None
        if raw_index - 1 < len(tree_columns):
            key = str(tree_columns[raw_index - 1])
            return key if self.has(key) else None
        return None

    def value_of(self, row: DocRow, key: str) -> str:
        """Liefert den Anzeigetext der Zelle (*row*, *key*).

        Args:
            row: Tabellenzeile.
            key: Spaltenschlüssel.

        Returns:
            Zelltext oder ``""`` für unbekannte Spalten/fehlende Werte.
        """
        if key == NACHNAME_KEY:
            return row.nachname
        if key == VORNAME_KEY:
            return row.vorname
        if key in self._date_index:
            idx = self._date_index[key]
            return row.date_cells[idx] if idx < len(row.date_cells) else ""
        if key in self._fixed_index:
            idx = self._fixed_index[key]
            return row.fixed_cells[idx] if idx < len(row.fixed_cells) else ""
        return ""

    def sort_value(self, row: DocRow, key: str) -> tuple:
        """Liefert den Sortierwert der Zelle (*row*, *key*) — konserviert die bisherige Semantik.

        - Namen: kleingeschrieben, lexikografisch.
        - Datum: roher Zelltext (ohne ``lower()``).
        - Feste Spalten: ``(0, float)`` falls als Zahl lesbar, sonst ``(1, text.lower())``;
          leere Zellen landen damit aufsteigend hinter allen Zahlen.
        - Unbekannte Spalte: ``("",)``.

        Args:
            row: Tabellenzeile.
            key: Spaltenschlüssel.

        Returns:
            Vergleichbares Tupel.
        """
        if not self.has(key):
            return ("",)
        kind = self._column(key).kind
        raw = self.value_of(row, key)
        if kind == "name":
            return (raw.lower(),)
        if kind == "date":
            return (raw,)
        try:
            return (0, float(raw))
        except (ValueError, TypeError):
            return (1, raw.lower())
