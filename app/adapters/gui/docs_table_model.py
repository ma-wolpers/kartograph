"""Logisches Tabellenmodell der Datenansicht (reines Python, kein Tk).

Die Datenansicht ist fachlich **eine logische Tabelle** aus Bereichen
(``DataArea``: Namen | Doku | Notizen | Noten, Regeln in
``core/domain/data_view_areas``). Welche Bereiche sichtbar sind, entscheidet
die Achse beim Aufbau; auf welche ``DataGrid``-Region ein Bereich fällt, leitet
die GUI aus den sichtbaren Bereichen ab (``_mixin_layout_docs``). Dieses Modul
hält die Struktur dieser Tabelle, unabhängig von jedem Widget:

- ``DocRow``: eine Tabellenzeile je Schüler (Namen + Zelltexte nach Spaltenschlüssel).
- ``GradeCellTarget``: der Noteneintrag, den ein Inline-Editor bearbeitet
  (beim Öffnen festgelegt).
- ``DocColumnAxis``: die eine logische horizontale Spaltenachse
  ``nachname → vorname → date_0 … date_n → notes → summary → grade_* → totals → overall``
  (nur sichtbare Bereiche) inkl. Bereichszuordnung, Nachbarschaft und
  Sortierwerten. Rein strukturell — kennt keinen UI-Zustand (keinen
  Datumsanker, keine Auswahl, keinen Fokus).

Zustandsabhängige Regeln (Sortierung, Sortier-Klickregel, ←/→-Navigation mit
Datumsanker) liegen getrennt davon in ``docs_table_rules``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

from app.core.domain.data_view_areas import DEFAULT_VISIBLE_AREAS, DataArea, shown_areas
from app.core.domain.grade_scale import parse_decimal_input
from app.core.domain.models_v4 import GradeCategory, StudentId

NACHNAME_KEY = "nachname"
VORNAME_KEY = "vorname"
NOTES_KEY = "notes"
SUMMARY_KEY = "summary"
OVERALL_KEY = "overall"
# Einzige Zuordnung Kategorie -> Spaltenschlüssel der Teilnote ("… gesamt");
# Tabellenaufbau und Spaltenkopf lesen nur diese Tabelle.
CATEGORY_TOTAL_KEYS: dict[GradeCategory, str] = {"schriftlich": "written_total", "sonstig": "sonstige_total"}

_GRADE_PREFIX = "grade_"

_ColumnKind = Literal["name", "date", "text", "summary", "grade", "total"]


def grade_column_key(column_id: str) -> str:
    """Spaltenschlüssel der Tabelle zur Notenspalte *column_id*.

    Args:
        column_id: Modell-ID der Notenspalte.
    """
    return f"{_GRADE_PREFIX}{column_id}"


def grade_column_id(key: str | None) -> str | None:
    """Modell-ID der Notenspalte zum Spaltenschlüssel *key*, ``None`` bei anderen Spalten.

    Args:
        key: Spaltenschlüssel der Tabelle.
    """
    return key[len(_GRADE_PREFIX):] if key and key.startswith(_GRADE_PREFIX) else None


@dataclass(frozen=True)
class DocRow:
    """Eine logische Zeile der Datentabelle (reine Anzeige-Strings).

    Attributes:
        iid: Zeilen-ID (Schüler-ID als String).
        nachname: Angezeigter Nachname (inkl. Fallback ``"(x,y)"`` bei leerem Nachnamen).
        vorname: Angezeigter Vorname.
        cells: Zelltexte aller übrigen Spalten nach Spaltenschlüssel; fehlender
            Schlüssel = leere Zelle. Gelesen wird nur über ``DocColumnAxis.value_of``.
        inactive: Person zählt nicht mit (dauerhaft abwesend, ``permanent_absence.is_active``):
            Zeile steht unabhängig von der Sortierung ganz unten und ist ausgegraut.
    """

    iid: str
    nachname: str
    vorname: str
    cells: Mapping[str, str] = field(default_factory=dict)
    inactive: bool = False


@dataclass(frozen=True)
class GradeCellTarget:
    """Ziel eines Inline-Noteneditors -- festgelegt beim Öffnen, nie aus der späteren Auswahl.

    Attributes:
        student_id: Schüler, dessen Note bearbeitet wird.
        column_id: Modell-ID der Notenspalte (ohne ``grade_``-Präfix).
    """

    student_id: StudentId
    column_id: str


@dataclass(frozen=True)
class DocColumn:
    """Eine logische Spalte der Datentabelle.

    Attributes:
        key: Spaltenschlüssel (``"nachname"``, ``"date_3"``, ``"notes"``, ``"grade_x"``, …).
        area: Bereich, zu dem die Spalte gehört.
        kind: Spaltenart; wird ausschließlich innerhalb dieses Moduls ausgewertet.
    """

    key: str
    area: DataArea
    kind: _ColumnKind


def _grade_area_kind(key: str) -> _ColumnKind:
    """Ordnet einer Spalte des Notenbereichs ihre Spaltenart zu.

    Args:
        key: Spalten-ID im Notenbereich (``"summary"``, ``"grade_*"``, ``"written_total"``, …).

    Returns:
        ``"summary"``, ``"grade"`` oder ``"total"`` (Zwischensummen und Gesamtnote).
    """
    if key == SUMMARY_KEY:
        return "summary"
    if grade_column_id(key) is not None:
        return "grade"
    return "total"


class DocColumnAxis:
    """Die logische horizontale Spaltenachse über alle sichtbaren Bereiche (zustandsfrei).

    Reihenfolge: ``nachname, vorname`` (Namen) → Datumsspalten (Doku) →
    Notizspalten (Notizen) → Notenbereich (Zusammenfassung, Noten, Summen,
    Gesamtnote). Spalten ausgeblendeter Bereiche gehören nicht zur Achse.
    Enthält nur Struktur; zustandsabhängige Regeln (Datumsanker-Rücksprung)
    liegen in ``resolve_horizontal_target``.
    """

    def __init__(
        self,
        date_column_ids: Sequence[str],
        grade_area_ids: Sequence[str],
        note_area_ids: Sequence[str] = (),
        visible_areas: tuple[DataArea, ...] = DEFAULT_VISIBLE_AREAS,
    ) -> None:
        """Baut die Achse aus den Spalten-IDs je Bereich und den sichtbaren Bereichen.

        Args:
            date_column_ids: IDs der Datumsspalten (``date_0`` …) in Anzeigereihenfolge.
            grade_area_ids: IDs der Spalten des Notenbereichs in Anzeigereihenfolge.
            note_area_ids: IDs der Spalten des Notizenbereichs in Anzeigereihenfolge.
            visible_areas: Sichtbare ausblendbare Bereiche (Namen sind immer dabei).
        """
        by_area: dict[DataArea, list[DocColumn]] = {
            DataArea.NAMEN: [DocColumn(NACHNAME_KEY, DataArea.NAMEN, "name"), DocColumn(VORNAME_KEY, DataArea.NAMEN, "name")],
            DataArea.DOKU: [DocColumn(key, DataArea.DOKU, "date") for key in date_column_ids],
            DataArea.NOTIZEN: [DocColumn(key, DataArea.NOTIZEN, "text") for key in note_area_ids],
            DataArea.NOTEN: [DocColumn(key, DataArea.NOTEN, _grade_area_kind(key)) for key in grade_area_ids],
        }
        self.areas: tuple[DataArea, ...] = shown_areas(visible_areas)
        self._columns: tuple[DocColumn, ...] = tuple(column for area in self.areas for column in by_area[area])
        self._position_by_key = {column.key: pos for pos, column in enumerate(self._columns)}
        self._date_ids: tuple[str, ...] = tuple(c.key for c in self._columns if c.kind == "date")
        self._date_index = {key: idx for idx, key in enumerate(self._date_ids)}

    @property
    def keys(self) -> tuple[str, ...]:
        """Alle Spaltenschlüssel in Achsenreihenfolge."""
        return tuple(column.key for column in self._columns)

    def has(self, key: str | None) -> bool:
        """Prüft, ob *key* eine Spalte dieser Achse ist.

        Args:
            key: Spaltenschlüssel oder ``None``.

        Returns:
            ``True``, falls die Spalte existiert (und ihr Bereich sichtbar ist).
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

    def area_of(self, key: str) -> DataArea:
        """Liefert den Bereich, zu dem *key* gehört.

        Args:
            key: Existierender Spaltenschlüssel.

        Returns:
            Der zuständige ``DataArea``.
        """
        return self._column(key).area

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
        """Prüft, ob *key* eine (sichtbare) Datumsspalte ist.

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
            Datumsspalten-Schlüssel oder ``None``, falls keine Datumsspalten
            sichtbar sind (auch bei ausgeblendetem Doku-Bereich).
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

    def first_selectable_in(self, area: DataArea) -> str | None:
        """Liefert die erste auswählbare Spalte eines Bereichs (überspringt z. B. ``summary``).

        Args:
            area: Bereich.

        Returns:
            Spaltenschlüssel oder ``None``, falls der Bereich keine hat oder ausgeblendet ist.
        """
        return next((c.key for c in self._columns if c.area is area and self.is_selectable(c.key)), None)

    def neighbor(self, key: str | None, step: int) -> str | None:
        """Liefert die strukturell benachbarte auswählbare Spalte.

        Kennt keinen Datumsanker — ``date_i`` hat immer ``date_i±1`` bzw. die
        Bereichsgrenze als Nachbarn.

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

    def columns_of(self, area: DataArea) -> tuple[str, ...]:
        """Spaltenschlüssel eines Bereichs in Achsenreihenfolge.

        Args:
            area: Bereich.

        Returns:
            Schlüssel der Spalten des Bereichs (leer, wenn ausgeblendet).
        """
        return tuple(column.key for column in self._columns if column.area is area)

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
        return row.cells.get(key, "") if self.has(key) else ""

    def sort_value(self, row: DocRow, key: str) -> tuple:
        """Liefert den Sortierwert der Zelle (*row*, *key*).

        - Namen und Textspalten: kleingeschrieben, lexikografisch.
        - Datum: roher Zelltext (ohne ``lower()``).
        - Notenbereich: ``(0, float)`` falls als Zahl lesbar (Komma oder Punkt,
          ``grade_scale.parse_decimal_input`` -- "1,7" ist eine Zahl), sonst
          ``(1, text.lower())``; leere Zellen landen damit aufsteigend hinter allen Zahlen.
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
        if kind in ("name", "text"):
            return (raw.lower(),)
        if kind == "date":
            return (raw,)
        try:
            return (0, parse_decimal_input(raw))
        except (ValueError, TypeError):
            return (1, raw.lower())
