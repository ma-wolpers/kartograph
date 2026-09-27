"""Tests für das logische Tabellenmodell der Dokuansicht (``docs_table_model`` / ``docs_table_rules``).

Reine Python-Tests ohne Tk: Spaltenachse, Klick-Auflösung, Nachbarschaft,
Zellwerte/Projektionen, Sortiersemantik (konserviert das Verhalten vor dem
Drei-Pane-Umbau) und Sortier-Klickregel.
"""

from __future__ import annotations

import pytest

from app.adapters.gui.docs_table_model import DocColumnAxis, DocRow, DocsPane
from app.adapters.gui.docs_table_rules import next_sort_spec, sort_iids

DATES = ("date_0", "date_1", "date_2")
FIXED = ("summary", "grade_a", "grade_b", "written_total", "overall")


@pytest.fixture
def axis() -> DocColumnAxis:
    return DocColumnAxis(DATES, FIXED)


def _row(iid: str, nachname: str = "", vorname: str = "", dates=("", "", ""), fixed=("", "", "", "", "")) -> DocRow:
    return DocRow(iid=iid, nachname=nachname, vorname=vorname, date_cells=tuple(dates), fixed_cells=tuple(fixed))


class TestAxisStructure:
    def test_axis_order_spans_all_three_panes(self, axis):
        assert axis.keys == ("nachname", "vorname", *DATES, *FIXED)

    def test_pane_of(self, axis):
        assert axis.pane_of("nachname") is DocsPane.NAMES
        assert axis.pane_of("vorname") is DocsPane.NAMES
        assert axis.pane_of("date_1") is DocsPane.MAIN
        assert axis.pane_of("grade_a") is DocsPane.RIGHT
        assert axis.pane_of("overall") is DocsPane.RIGHT

    def test_pane_columns_match_treeview_configuration(self, axis):
        assert axis.pane_columns(DocsPane.NAMES) == ("vorname",)
        assert axis.pane_columns(DocsPane.MAIN) == DATES
        assert axis.pane_columns(DocsPane.RIGHT) == FIXED

    def test_tree_column_maps_only_nachname_to_tree_column(self, axis):
        assert axis.tree_column("nachname") == "#0"
        assert axis.tree_column("vorname") == "vorname"
        assert axis.tree_column("date_0") == "date_0"

    def test_summary_is_not_selectable(self, axis):
        assert not axis.is_selectable("summary")
        assert axis.is_selectable("nachname")
        assert axis.is_selectable("overall")
        assert not axis.is_selectable("grade_zz")

    def test_first_selectable_nondate_right_skips_summary(self, axis):
        assert axis.first_selectable_nondate_right() == "grade_a"

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


class TestResolveClicked:
    """Regression gegen Offset-Arithmetik: "#N" wird über das columns-Tupel des Widgets aufgelöst."""

    def test_names_tree_column_is_nachname(self, axis):
        assert axis.resolve_clicked(DocsPane.NAMES, "#0", ("vorname",)) == "nachname"

    def test_names_first_column_is_vorname(self, axis):
        assert axis.resolve_clicked(DocsPane.NAMES, "#1", ("vorname",)) == "vorname"

    def test_main_first_column_is_first_date(self, axis):
        assert axis.resolve_clicked(DocsPane.MAIN, "#1", DATES) == "date_0"
        assert axis.resolve_clicked(DocsPane.MAIN, "#3", DATES) == "date_2"

    def test_right_columns_resolve_to_fixed_keys(self, axis):
        assert axis.resolve_clicked(DocsPane.RIGHT, "#1", FIXED) == "summary"
        assert axis.resolve_clicked(DocsPane.RIGHT, "#5", FIXED) == "overall"

    def test_tree_column_outside_names_pane_is_none(self, axis):
        assert axis.resolve_clicked(DocsPane.MAIN, "#0", DATES) is None

    def test_click_beside_columns_is_none(self, axis):
        assert axis.resolve_clicked(DocsPane.MAIN, "", DATES) is None
        assert axis.resolve_clicked(DocsPane.MAIN, "#9", DATES) is None


class TestValuesAndProjections:
    def test_value_of_resolves_semantically(self, axis):
        row = _row("1", "Meier", "Ada", ("a", "b", "c"), ("S", "1.00", "2.00", "1.5", "1,7"))
        assert axis.value_of(row, "nachname") == "Meier"
        assert axis.value_of(row, "vorname") == "Ada"
        assert axis.value_of(row, "date_1") == "b"
        assert axis.value_of(row, "grade_b") == "2.00"
        assert axis.value_of(row, "overall") == "1,7"
        assert axis.value_of(row, "gibtsnicht") == ""

    def test_projections_split_row_per_pane(self):
        row = _row("1", "Meier", "Ada", ("a", "b", "c"), ("S", "1", "2", "3", "4"))
        assert row.names_projection() == ("Meier", ["Ada"])
        assert row.main_projection() == ["a", "b", "c"]
        assert row.right_projection() == ["S", "1", "2", "3", "4"]


class TestSortSemantics:
    """Konserviert die Sortiersemantik vor dem Drei-Pane-Umbau."""

    def test_nachname_case_insensitive_incl_coordinate_fallback(self, axis):
        rows = [_row("1", "meier"), _row("2", "(0,1)"), _row("3", "Adam")]
        assert sort_iids(rows, "nachname", True, axis) == ["2", "3", "1"]
        assert sort_iids(rows, "nachname", False, axis) == ["1", "3", "2"]

    def test_vorname_case_insensitive_empty_first(self, axis):
        rows = [_row("1", vorname="bea"), _row("2", vorname=""), _row("3", vorname="Anna")]
        assert sort_iids(rows, "vorname", True, axis) == ["2", "3", "1"]

    def test_date_raw_string_without_lower(self, axis):
        rows = [_row("1", dates=("b", "", "")), _row("2", dates=("", "", "")), _row("3", dates=("B", "", ""))]
        # Roh-Vergleich: "" < "B" < "b" (kein lower())
        assert sort_iids(rows, "date_0", True, axis) == ["2", "3", "1"]

    def test_grade_numbers_before_text_empty_after_numbers(self, axis):
        rows = [
            _row("empty", fixed=("", "", "", "", "")),
            _row("two", fixed=("", "2.00", "", "", "")),
            _row("one", fixed=("", "1.00", "", "", "")),
            _row("text", fixed=("", "x", "", "", "")),
        ]
        assert sort_iids(rows, "grade_a", True, axis) == ["one", "two", "empty", "text"]
        # absteigend: ganzes Tupel umgekehrt -> Text/leer vor den Zahlen
        assert sort_iids(rows, "grade_a", False, axis) == ["text", "empty", "two", "one"]

    def test_comma_decimal_is_treated_as_text(self, axis):
        rows = [_row("comma", fixed=("", "", "", "", "1,7")), _row("dot", fixed=("", "", "", "", "3.0"))]
        assert sort_iids(rows, "overall", True, axis) == ["dot", "comma"]

    def test_total_column_sorts_numerically(self, axis):
        rows = [_row("a", fixed=("", "", "", "10", "")), _row("b", fixed=("", "", "", "9", ""))]
        assert sort_iids(rows, "written_total", True, axis) == ["b", "a"]

    def test_ties_keep_base_order(self, axis):
        rows = [_row("3", "Same"), _row("1", "same"), _row("2", "SAME")]
        assert sort_iids(rows, "nachname", True, axis) == ["3", "1", "2"]
        assert sort_iids(rows, "nachname", False, axis) == ["3", "1", "2"]

    def test_no_or_unknown_sort_key_keeps_base_order(self, axis):
        rows = [_row("b", "Z"), _row("a", "A")]
        assert sort_iids(rows, None, True, axis) == ["b", "a"]
        assert sort_iids(rows, "grade_weg", True, axis) == ["b", "a"]

    @pytest.mark.parametrize("key", ["nachname", "vorname", *DATES, *FIXED])
    @pytest.mark.parametrize("ascending", [True, False])
    def test_every_sortable_column_yields_monotonic_permutation(self, axis, key, ascending):
        rows = [
            _row("1", "Meier", "Ada", ("x", "", "o"), ("S", "2.00", "", "3", "2,0")),
            _row("2", "adam", "", ("", "+", "o"), ("", "1.00", "4.00", "", "1.5")),
            _row("3", "Zett", "bo", ("+", "x", ""), ("SS", "x", "1.00", "2", "")),
        ]
        order = sort_iids(rows, key, ascending, axis)
        assert sorted(order) == ["1", "2", "3"]
        by_iid = {row.iid: row for row in rows}
        values = [axis.sort_value(by_iid[iid], key) for iid in order]
        assert values == sorted(values, reverse=not ascending)


class TestSortClickRule:
    def test_click_sequence(self):
        spec = next_sort_spec(None, True, "nachname")
        assert spec == ("nachname", True)
        spec = next_sort_spec(*spec, "nachname")
        assert spec == ("nachname", False)
        spec = next_sort_spec(*spec, "vorname")
        assert spec == ("vorname", True)
        spec = next_sort_spec(*spec, "vorname")
        assert spec == ("vorname", False)
        spec = next_sort_spec(*spec, "vorname")
        assert spec == ("vorname", True)

    def test_new_column_always_starts_ascending(self):
        assert next_sort_spec("date_0", False, "grade_a") == ("grade_a", True)
