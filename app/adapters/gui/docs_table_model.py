"""Logisches Tabellenmodell der Dokuansicht (reines Python, kein Tk).

Die Dokuansicht ist fachlich **eine logische Tabelle**, dargestellt in
drei Bereichen eines bw-gui ``DataGrid`` (``DocsPane.NAMES`` / ``MAIN`` /
``RIGHT``). Dieses Modul hält die Struktur dieser Tabelle, unabhängig von
jedem Widget:

- ``DocRow``: eine Tabellenzeile (Anzeige-Strings) je Schüler.
- ``GradeCellTarget``: der Noteneintrag, den ein Inline-Editor bearbeitet
  (beim Öffnen festgelegt).
- ``DocColumnAxis``: die eine logische horizontale Spaltenachse
  ``nachname → vorname → date_0 … date_n → summary → grade_* → totals → overall``
  inkl. Pane-Zuordnung, Nachbarschaft und Sortierwerten. Rein strukturell —
  kennt keinen UI-Zustand (keinen Datumsanker, keine Auswahl, keinen Fokus).

Zustandsabhängige Regeln (Sortierung, Sortier-Klickregel, ←/→-Navigation mit
Datumsanker) liegen getrennt davon in ``docs_table_rules``.

Grenze der Positionsrepräsentation: ``DocRow.date_cells`` und
``DocRow.fixed_cells`` sind intern positionsbasierte Tupel. **Nur**
``DocColumnAxis.value_of`` (und darauf aufbauend ``cells_of``/``sort_value``)
darf einen Tupelindex einer Spalte zuordnen; alles außerhalb dieses Moduls
arbeitet ausschließlich mit Spaltenschlüsseln.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Sequence

from app.core.domain.models_v4 import StudentId

NACHNAME_KEY = "nachname"
VORNAME_KEY = "vorname"
SUMMARY_KEY = "summary"

_ColumnKind = Literal["name", "date", "summary", "grade", "total"]


class DocsPane(Enum):
    """Die drei Bereiche der Dokutabelle (Namen | Datumsspalten | feste Spalten)."""

    NAMES = "names"
    MAIN = "main"
    RIGHT = "right"


@dataclass(frozen=True)
class DocRow:
    """Eine logische Zeile der Dokutabelle (reine Anzeige-Strings).

    Attributes:
        iid: Zeilen-ID (Schüler-ID als String).
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


@dataclass(frozen=True)
class GradeCellTarget:
    """Ziel eines Inline-Noteneditors -- festgelegt beim Öffnen, nie aus der späteren Auswahl.

    Attributes:
        student_id: Schüler, dessen Note bearbeitet wird.
        date: Datum (YYYY-MM-DD) des Noteneintrags.
        column_id: Modell-ID der Notenspalte (ohne ``grade_``-Präfix).
    """

    student_id: StudentId
    date: str
    column_id: str


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

    def columns_of(self, pane: DocsPane) -> tuple[str, ...]:
        """Spaltenschlüssel eines Panes in Achsenreihenfolge.

        Args:
            pane: Ziel-Pane.

        Returns:
            Schlüssel der Spalten, die *pane* darstellt.
        """
        return tuple(column.key for column in self._columns if column.pane is pane)

    def cells_of(self, row: DocRow) -> dict[str, str]:
        """Alle Zelltexte einer Zeile nach Spaltenschlüssel (für die Grid-Projektion).

        Args:
            row: Tabellenzeile.

        Returns:
            Spaltenschlüssel → Anzeigetext, für jede Spalte der Achse.
        """
        return {column.key: self.value_of(row, column.key) for column in self._columns}

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
