"""Tests für das logische Tabellenmodell der Datenansicht (``docs_table_model`` / ``docs_table_rules``).

Reine Python-Tests ohne Tk: Spaltenachse, Klick-Auflösung, Nachbarschaft,
Zellwerte/Projektionen, Sortiersemantik (konserviert das Verhalten vor dem
Drei-Pane-Umbau) und Sortier-Klickregel.
"""

from __future__ import annotations

import pytest

from app.adapters.gui.docs_table_model import DocColumnAxis, DocRow
from app.core.domain.data_view_areas import DataArea
from app.adapters.gui.docs_table_rules import (
    SortKey,
    next_sort_stack,
    prune_sort_stack,
    retain_known_sort_keys,
    sort_iids,
)

DATES = ("date_0", "date_1", "date_2")
FIXED = ("summary", "grade_a", "grade_b", "written_total", "overall")


def _s(key: str | None, ascending: bool = True) -> tuple[SortKey, ...]:
    """Einstufiger Sortierstapel (``None`` = leerer Stapel = Sitzordnung)."""
    return () if key is None else (SortKey(key, ascending),)


@pytest.fixture
def axis() -> DocColumnAxis:
    return DocColumnAxis(DATES, FIXED)


def _row(iid: str, nachname: str = "", vorname: str = "", dates=("", "", ""), fixed=("", "", "", "", ""),
         inactive: bool = False) -> DocRow:
    """Zeile mit Datums-/Notenbereichszellen in Achsenreihenfolge (leere Zellen entfallen)."""
    cells = {key: text for key, text in zip((*DATES, *FIXED), (*dates, *fixed)) if text}
    return DocRow(iid=iid, nachname=nachname, vorname=vorname, cells=cells, inactive=inactive)


class TestAxisStructure:
    def test_axis_order_spans_names_doku_and_grades_by_default(self, axis):
        assert axis.keys == ("nachname", "vorname", *DATES, *FIXED)
        assert axis.areas == (DataArea.NAMEN, DataArea.DOKU, DataArea.NOTEN)

    def test_area_of(self, axis):
        assert axis.area_of("nachname") is DataArea.NAMEN
        assert axis.area_of("vorname") is DataArea.NAMEN
        assert axis.area_of("date_1") is DataArea.DOKU
        assert axis.area_of("grade_a") is DataArea.NOTEN
        assert axis.area_of("overall") is DataArea.NOTEN

    def test_columns_of_each_area(self, axis):
        assert axis.columns_of(DataArea.NAMEN) == ("nachname", "vorname")
        assert axis.columns_of(DataArea.DOKU) == DATES
        assert axis.columns_of(DataArea.NOTEN) == FIXED

    def test_summary_is_not_selectable(self, axis):
        assert not axis.is_selectable("summary")
        assert axis.is_selectable("nachname")
        assert axis.is_selectable("overall")
        assert not axis.is_selectable("grade_zz")

    def test_first_selectable_in_skips_summary(self, axis):
        assert axis.first_selectable_in(DataArea.NOTEN) == "grade_a"
        assert axis.first_selectable_in(DataArea.NOTIZEN) is None


class TestVisibleAreas:
    """Ausgeblendete Bereiche gehören nicht zur Achse; die Notizen stehen zwischen Doku und Noten."""

    def test_hidden_areas_drop_their_columns(self):
        axis = DocColumnAxis(DATES, FIXED, ("notes",), (DataArea.NOTIZEN, DataArea.NOTEN))
        assert axis.keys == ("nachname", "vorname", "notes", *FIXED)
        assert axis.areas == (DataArea.NAMEN, DataArea.NOTIZEN, DataArea.NOTEN)
        assert not axis.has("date_0") and axis.date_key(0) is None

    def test_notes_sit_between_doku_and_grades(self):
        axis = DocColumnAxis(DATES, FIXED, ("notes",), (DataArea.DOKU, DataArea.NOTIZEN))
        assert axis.keys == ("nachname", "vorname", *DATES, "notes")
        assert axis.neighbor("date_2", 1) == "notes"

    def test_only_names_when_everything_is_hidden(self):
        axis = DocColumnAxis(DATES, FIXED, ("notes",), ())
        assert axis.keys == ("nachname", "vorname")

    def test_values_of_hidden_columns_are_empty(self):
        axis = DocColumnAxis(DATES, FIXED, ("notes",), (DataArea.NOTIZEN,))
        row = DocRow("1", "Meier", "Ada", {"date_0": "x", "notes": "Braucht Zeit"})
        assert axis.value_of(row, "date_0") == ""
        assert axis.cells_of(row) == {"nachname": "Meier", "vorname": "Ada", "notes": "Braucht Zeit"}

    def test_notes_sort_case_insensitive(self):
        axis = DocColumnAxis(DATES, FIXED, ("notes",), (DataArea.NOTIZEN,))
        rows = [DocRow("b", "", "", {"notes": "zeit"}), DocRow("a", "", "", {"notes": "Arbeit"})]
        assert sort_iids(rows, _s("notes"), axis) == ["a", "b"]

    def test_date_key_clamps(self, axis):
        assert axis.date_key(1) == "date_1"
        assert axis.date_key(99) == "date_2"
        assert axis.date_key(-3) == "date_0"
        assert DocColumnAxis((), FIXED).date_key(0) is None


class TestNeighbor:
    @pytest.mark.parametrize(
        ("start", "step", "expected"),
        [
            ("nachname", 1, "vorname"),
            ("vorname", 1, "date_0"),
            ("date_0", -1, "vorname"),
            ("vorname", -1, "nachname"),
            ("nachname", -1, None),
            ("date_0", 1, "date_1"),
            ("date_2", 1, "grade_a"),  # summary übersprungen
            ("grade_a", -1, "date_2"),  # strukturell; Datumsanker-Regel liegt in docs_table_rules
            ("grade_b", 1, "written_total"),
            ("overall", 1, None),
            ("unbekannt", 1, None),
        ],
    )
    def test_structural_neighbors(self, axis, start, step, expected):
        assert axis.neighbor(start, step) == expected


class TestValuesAndProjections:
    def test_value_of_resolves_semantically(self, axis):
        row = _row("1", "Meier", "Ada", ("a", "b", "c"), ("S", "1.00", "2.00", "1.5", "1,7"))
        assert axis.value_of(row, "nachname") == "Meier"
        assert axis.value_of(row, "vorname") == "Ada"
        assert axis.value_of(row, "date_1") == "b"
        assert axis.value_of(row, "grade_b") == "2.00"
        assert axis.value_of(row, "overall") == "1,7"
        assert axis.value_of(row, "gibtsnicht") == ""

    def test_cells_of_maps_every_column_key(self, axis):
        row = _row("1", "Meier", "Ada", ("a", "b", "c"), ("S", "1", "2", "3", "4"))
        cells = axis.cells_of(row)
        assert list(cells) == list(axis.keys)
        assert cells["nachname"] == "Meier" and cells["date_2"] == "c" and cells["overall"] == "4"


class TestSortSemantics:
    """Konserviert die Sortiersemantik vor dem Drei-Pane-Umbau."""

    def test_nachname_case_insensitive_incl_coordinate_fallback(self, axis):
        rows = [_row("1", "meier"), _row("2", "(0,1)"), _row("3", "Adam")]
        assert sort_iids(rows, _s("nachname", True), axis) == ["2", "3", "1"]
        assert sort_iids(rows, _s("nachname", False), axis) == ["1", "3", "2"]

    def test_vorname_case_insensitive_empty_first(self, axis):
        rows = [_row("1", vorname="bea"), _row("2", vorname=""), _row("3", vorname="Anna")]
        assert sort_iids(rows, _s("vorname", True), axis) == ["2", "3", "1"]

    def test_date_raw_string_without_lower(self, axis):
        rows = [_row("1", dates=("b", "", "")), _row("2", dates=("", "", "")), _row("3", dates=("B", "", ""))]
        # Roh-Vergleich: "" < "B" < "b" (kein lower())
        assert sort_iids(rows, _s("date_0", True), axis) == ["2", "3", "1"]

    def test_grade_numbers_before_text_empty_after_numbers(self, axis):
        rows = [
            _row("empty", fixed=("", "", "", "", "")),
            _row("two", fixed=("", "2.00", "", "", "")),
            _row("one", fixed=("", "1.00", "", "", "")),
            _row("text", fixed=("", "x", "", "", "")),
        ]
        assert sort_iids(rows, _s("grade_a", True), axis) == ["one", "two", "empty", "text"]
        # absteigend: ganzes Tupel umgekehrt -> Text/leer vor den Zahlen
        assert sort_iids(rows, _s("grade_a", False), axis) == ["text", "empty", "two", "one"]

    def test_comma_decimal_sorts_as_number(self, axis):
        rows = [_row("dot", fixed=("", "", "", "", "3.0")), _row("comma", fixed=("", "", "", "", "1,7"))]
        assert sort_iids(rows, _s("overall", True), axis) == ["comma", "dot"]

    def test_total_column_sorts_numerically(self, axis):
        rows = [_row("a", fixed=("", "", "", "10", "")), _row("b", fixed=("", "", "", "9", ""))]
        assert sort_iids(rows, _s("written_total", True), axis) == ["b", "a"]

    def test_ties_keep_base_order(self, axis):
        rows = [_row("3", "Same"), _row("1", "same"), _row("2", "SAME")]
        assert sort_iids(rows, _s("nachname", True), axis) == ["3", "1", "2"]
        assert sort_iids(rows, _s("nachname", False), axis) == ["3", "1", "2"]

    def test_no_or_unknown_sort_key_keeps_base_order(self, axis):
        rows = [_row("b", "Z"), _row("a", "A")]
        assert sort_iids(rows, _s(None, True), axis) == ["b", "a"]
        assert sort_iids(rows, _s("grade_weg", True), axis) == ["b", "a"]

    @pytest.mark.parametrize("key", ["nachname", "vorname", *DATES, *FIXED])
    @pytest.mark.parametrize("ascending", [True, False])
    def test_every_sortable_column_yields_monotonic_permutation(self, axis, key, ascending):
        rows = [
            _row("1", "Meier", "Ada", ("x", "", "o"), ("S", "2.00", "", "3", "2,0")),
            _row("2", "adam", "", ("", "+", "o"), ("", "1.00", "4.00", "", "1.5")),
            _row("3", "Zett", "bo", ("+", "x", ""), ("SS", "x", "1.00", "2", "")),
        ]
        order = sort_iids(rows, _s(key, ascending), axis)
        assert sorted(order) == ["1", "2", "3"]
        by_iid = {row.iid: row for row in rows}
        values = [axis.sort_value(by_iid[iid], key) for iid in order]
        assert values == sorted(values, reverse=not ascending)


class TestSortClickRule:
    def test_click_sequence(self):
        stack = next_sort_stack((), "nachname")
        assert stack == (SortKey("nachname", True),)
        stack = next_sort_stack(stack, "nachname")
        assert stack == (SortKey("nachname", False),)
        stack = next_sort_stack(stack, "vorname")
        assert stack == (SortKey("vorname", True), SortKey("nachname", False))
        stack = next_sort_stack(stack, "vorname")
        assert stack == (SortKey("vorname", False), SortKey("nachname", False))

    def test_new_column_always_starts_ascending(self):
        assert next_sort_stack((SortKey("date_0", False),), "grade_a")[0] == SortKey("grade_a", True)

    def test_deeper_column_moves_to_front_ascending_without_duplicate(self):
        stack = (SortKey("grade_b", False), SortKey("grade_a", False), SortKey("nachname"))
        assert next_sort_stack(stack, "grade_a") == (SortKey("grade_a"), SortKey("grade_b", False), SortKey("nachname"))


class TestMultiKeySort:
    """Frühere Klicks lösen Gleichstände auf; unnötige Stufen werden beim Klick vergessen."""

    def _rows(self):
        # grade_a = Note 1, grade_b = Note 2; Basisreihenfolge (Sitzordnung) absichtlich nicht nach Namen.
        return [
            _row("z", "Zorn", fixed=("", "2", "1", "", "")),
            _row("m", "Maier", fixed=("", "1", "2", "", "")),
            _row("b", "Berg", fixed=("", "2", "2", "", "")),
            _row("a", "Adam", fixed=("", "1", "2", "", "")),
        ]

    def _click(self, stack, key, rows, axis):
        return prune_sort_stack(next_sort_stack(stack, key), rows, axis)

    def test_name_then_grade_sorts_by_grade_then_name(self, axis):
        rows = self._rows()
        stack = self._click((), "nachname", rows, axis)
        stack = self._click(stack, "grade_a", rows, axis)
        assert stack == (SortKey("grade_a"), SortKey("nachname"))
        assert sort_iids(rows, stack, axis) == ["a", "m", "b", "z"]

    def test_second_grade_then_first_grade_then_name(self, axis):
        rows = self._rows()
        stack = ()
        for key in ("nachname", "grade_a", "grade_b"):
            stack = self._click(stack, key, rows, axis)
        assert stack == (SortKey("grade_b"), SortKey("grade_a"), SortKey("nachname"))
        assert sort_iids(rows, stack, axis) == ["z", "a", "m", "b"]

    def test_unneeded_key_is_forgotten_and_stays_forgotten(self, axis):
        rows = [_row("x", "Xu", fixed=("", "1", "1", "", "")), _row("y", "Yi", fixed=("", "2", "1", "", ""))]
        stack = self._click((), "nachname", rows, axis)
        stack = self._click(stack, "grade_a", rows, axis)
        assert stack == (SortKey("grade_a"),)  # Note 1 ordnet schon eindeutig -> Name vergessen
        tied = [_row("x", "Xu", fixed=("", "1", "1", "", "")), _row("y", "Yi", fixed=("", "1", "1", "", ""))]
        assert sort_iids(list(reversed(tied)), stack, axis) == ["y", "x"]  # Gleichstand -> Sitzordnung

    def test_head_is_kept_even_without_ties(self, axis):
        assert prune_sort_stack(_s("nachname", False), [_row("1", "A")], axis) == _s("nachname", False)

    def test_unknown_keys_are_dropped(self, axis):
        stack = (SortKey("grade_weg"), SortKey("nachname"), SortKey("grade_a"))
        assert retain_known_sort_keys(stack, axis) == (SortKey("nachname"), SortKey("grade_a"))
        assert prune_sort_stack(stack, self._rows(), axis) == (SortKey("nachname"),)


class TestInactiveRowsStayAtTheBottom:
    """Dauerhaft Abwesende (``DocRow.inactive``) stehen bei jeder Sortierung ganz unten."""

    def _rows(self):
        return [
            _row("a", "Alt", fixed=("", "1", "", "", ""), inactive=True),
            _row("b", "Berg", fixed=("", "3", "", "", "")),
            _row("c", "Cal", fixed=("", "2", "", "", ""), inactive=True),
            _row("d", "Dorn", fixed=("", "4", "", "", "")),
        ]

    def test_without_sort_column_base_order_with_inactive_last(self, axis):
        assert sort_iids(self._rows(), _s(None, True), axis) == ["b", "d", "a", "c"]

    @pytest.mark.parametrize(("ascending", "expected"), [(True, ["b", "d", "a", "c"]), (False, ["d", "b", "c", "a"])])
    def test_sorted_by_grade_both_directions(self, axis, ascending, expected):
        assert sort_iids(self._rows(), _s("grade_a", ascending), axis) == expected

    def test_sorted_by_name_descending_keeps_inactive_last(self, axis):
        assert sort_iids(self._rows(), _s("nachname", False), axis)[-2:] == ["c", "a"]
