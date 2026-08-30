"""Tests fuer _resolve_clicked_column_name() -- Off-by-one-Regression (Klick auf eine
Datumsspalte im linken Doku-Treeview waehlte bisher die Spalte rechts daneben, weil
"#N" pauschal um 1 statt um die Anzahl fuehrender Nicht-Datenspalten ("vorname")
verschoben wurde). Fest gegen das Widget-eigene columns-Tupel aufgeloest statt gegen
einen hart codierten Offset, der bei jeder Spaltenlayout-Aenderung von Hand
nachgezogen werden muesste.
"""

from __future__ import annotations

from app.adapters.gui._mixin_docs_events import DocsEventsMixin


class _FakeTree:
    """Minimales Double fuer ttk.Treeview: nur identify_column() und ["columns"] noetig."""

    def __init__(self, columns: tuple[str, ...], column_for_x: dict[int, str]):
        self._columns = columns
        self._column_for_x = column_for_x

    def identify_column(self, x: int) -> str:
        return self._column_for_x.get(x, "")

    def __getitem__(self, key: str):
        if key == "columns":
            return self._columns
        raise KeyError(key)


class TestResolveClickedColumnName:
    def test_left_tree_click_on_first_date_column_resolves_to_that_column_not_the_next(self):
        """Regression: "#2" (erste Datumsspalte, da "#1" = "vorname") muss auf
        "date_0" aufloesen, nicht faelschlich auf "date_1"."""
        tree = _FakeTree(columns=("vorname", "date_0", "date_1"), column_for_x={10: "#2"})

        assert DocsEventsMixin._resolve_clicked_column_name(tree, 10) == "date_0"

    def test_left_tree_click_on_vorname_column_resolves_to_vorname_not_a_date(self):
        tree = _FakeTree(columns=("vorname", "date_0", "date_1"), column_for_x={5: "#1"})

        assert DocsEventsMixin._resolve_clicked_column_name(tree, 5) == "vorname"

    def test_last_date_column_resolves_correctly_no_overflow(self):
        tree = _FakeTree(columns=("vorname", "date_0", "date_1"), column_for_x={20: "#3"})

        assert DocsEventsMixin._resolve_clicked_column_name(tree, 20) == "date_1"

    def test_right_tree_without_leading_column_still_resolves_correctly(self):
        """Rechter Treeview hat keine 'vorname'-Spalte davor -- "#1" ist direkt die erste Fixspalte."""
        tree = _FakeTree(columns=("summary", "overall"), column_for_x={7: "#1"})

        assert DocsEventsMixin._resolve_clicked_column_name(tree, 7) == "summary"

    def test_click_outside_any_data_column_returns_none(self):
        tree = _FakeTree(columns=("vorname", "date_0"), column_for_x={0: "#0"})

        assert DocsEventsMixin._resolve_clicked_column_name(tree, 0) is None

    def test_click_on_heading_region_marker_or_empty_area_returns_none(self):
        tree = _FakeTree(columns=("vorname", "date_0"), column_for_x={999: ""})

        assert DocsEventsMixin._resolve_clicked_column_name(tree, 999) is None
