"""Tests für den Namenfit-CSV-Export (Domain-Logik + Datei-Schreiber)."""

import csv

import pytest

from app.core.domain.models_v4 import GroupSeat, TableGroup
from app.core.domain.namenfit_csv_export import (
    DuplicateDisplayNamesError,
    UngroupedStudent,
    UngroupedStudentsError,
    _resolve_group_numbers,
    build_namenfit_rows,
)
from app.infrastructure.exporters.namenfit_csv_exporter import export_namenfit_csv
from tests.conftest import make_plan, make_student


def _rect_group(group_id: int, x0: int, y0: int, width: int, height: int) -> TableGroup:
    """Baut eine rechteckige Tischgruppe ab (x0, y0) mit gegebener Breite/Höhe."""
    seats = [GroupSeat(x=x0 + dx, y=y0 + dy) for dy in range(height) for dx in range(width)]
    return TableGroup(group_id=group_id, seats=seats)


class TestBuildNamenfitRowsBasics:
    def test_single_rectangular_table(self):
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=1, y=0, first_name="Ben", last_name="Meier")
        plan = make_plan(students=[s1, s2])
        plan.tablegroups = [_rect_group(1, 0, 0, width=2, height=1)]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        assert rows == [
            ["Tisch 1", ""],
            ["Anna Gold", "Ben Meier"],
        ]

    def test_header_label_only_on_first_column_of_block(self):
        """Namenfit übernimmt Leerzellen im Header vom letzten Label links davon --
        das Label darf daher nur einmal, in der ersten Spalte des Blocks, stehen."""
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=1, y=0, first_name="Ben", last_name="Meier")
        s3 = make_student(x=2, y=0, first_name="Carla", last_name="Weiss")
        plan = make_plan(students=[s1, s2, s3])
        plan.tablegroups = [_rect_group(1, 0, 0, width=3, height=1)]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        assert rows[0] == ["Tisch 1", "", ""]

    def test_two_tables_side_by_side_get_separate_header_labels(self):
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=10, y=0, first_name="Ben", last_name="Meier")
        plan = make_plan(students=[s1, s2])
        plan.tablegroups = [
            _rect_group(1, 0, 0, width=1, height=1),
            _rect_group(2, 10, 0, width=1, height=1),
        ]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        assert rows[0] == ["Tisch 1", "Tisch 2"]
        assert rows[1] == ["Anna Gold", "Ben Meier"]

    def test_tables_ordered_by_group_id_ascending(self):
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=10, y=0, first_name="Ben", last_name="Meier")
        plan = make_plan(students=[s1, s2])
        # Gruppe 5 physisch links, Gruppe 1 physisch rechts -- Spaltenreihenfolge soll trotzdem nach group_id gehen.
        plan.tablegroups = [
            _rect_group(5, 0, 0, width=1, height=1),
            _rect_group(1, 10, 0, width=1, height=1),
        ]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        assert rows[0] == ["Tisch 1", "Tisch 5"]
        assert rows[1] == ["Ben Meier", "Anna Gold"]

    def test_shorter_table_padded_with_blank_rows(self):
        """Eine 1-Platz-Tischgruppe neben einer 2-zeiligen Gruppe bekommt eine leere zweite Zeile."""
        tall = [
            make_student(x=0, y=0, first_name="Anna", last_name="Gold"),
            make_student(x=0, y=1, first_name="Ben", last_name="Meier"),
        ]
        solo = make_student(x=10, y=0, first_name="Carla", last_name="Weiss")
        plan = make_plan(students=[*tall, solo])
        plan.tablegroups = [
            _rect_group(1, 0, 0, width=1, height=2),
            _rect_group(2, 10, 0, width=1, height=1),
        ]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        assert rows == [
            ["Tisch 1", "Tisch 2"],
            ["Anna Gold", "Carla Weiss"],
            ["Ben Meier", ""],
        ]

    def test_irregular_l_shaped_table_leaves_hole_blank(self):
        """Eine L-foermige Gruppe (2x2 minus eine Ecke) laesst die fehlende Ecke als leere Zelle."""
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=1, y=0, first_name="Ben", last_name="Meier")
        s3 = make_student(x=0, y=1, first_name="Carla", last_name="Weiss")
        plan = make_plan(students=[s1, s2, s3])
        plan.tablegroups = [
            TableGroup(group_id=1, seats=[GroupSeat(x=0, y=0), GroupSeat(x=1, y=0), GroupSeat(x=0, y=1)])
        ]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        assert rows == [
            ["Tisch 1", ""],
            ["Anna Gold", "Ben Meier"],
            ["Carla Weiss", ""],
        ]

    def test_row_increases_downward_matching_grid_render_pixel_mapping(self):
        """Kartograph-y wird direkt (nicht invertiert) als Namenfit-Zeile uebernommen --
        groesseres y = Richtung Lehrertisch (unten) = groessere Zeile = "vorne" bei Namenfit."""
        front = make_student(x=0, y=1, first_name="Anna", last_name="Gold")  # naeher am Lehrertisch (unten)
        back = make_student(x=0, y=0, first_name="Ben", last_name="Meier")  # weiter vom Lehrertisch (oben)
        plan = make_plan(students=[front, back])
        plan.tablegroups = [_rect_group(1, 0, 0, width=1, height=2)]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        assert rows[1] == ["Ben Meier"]  # kleineres y -> Zeile 0 -> "hinten"
        assert rows[2] == ["Anna Gold"]  # groesseres y -> Zeile 1 -> "vorne"

    def test_unnamed_student_within_table_leaves_blank_cell(self):
        named = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        blank = make_student(x=1, y=0, first_name="", last_name="")
        plan = make_plan(students=[named, blank])
        plan.tablegroups = [_rect_group(1, 0, 0, width=2, height=1)]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        assert rows == [["Tisch 1", ""], ["Anna Gold", ""]]

    def test_teacher_seat_never_appears_in_export(self):
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        plan = make_plan(students=[s1])
        plan.tablegroups = [_rect_group(1, 0, 0, width=1, height=1)]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        flat = [cell for row in rows for cell in row]
        assert not any("lehrer" in cell.lower() for cell in flat)


class TestBuildNamenfitRowsNicknamesAndFormat:
    def test_nickname_supersedes_official_first_name(self):
        s1 = make_student(x=0, y=0, first_name="Alexander", last_name="Klein", nickname="Alex")
        plan = make_plan(students=[s1])
        plan.tablegroups = [_rect_group(1, 0, 0, width=1, height=1)]

        rows = build_namenfit_rows(plan, "Vorname Nachname")

        assert rows[1] == ["Alex Klein"]

    def test_name_format_is_respected(self):
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        plan = make_plan(students=[s1])
        plan.tablegroups = [_rect_group(1, 0, 0, width=1, height=1)]

        rows = build_namenfit_rows(plan, "Nachname")

        assert rows[1] == ["Gold"]


class TestBuildNamenfitRowsErrors:
    def test_duplicate_display_names_raises(self):
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=1, y=0, first_name="Anna", last_name="Gold")
        plan = make_plan(students=[s1, s2])
        plan.tablegroups = [_rect_group(1, 0, 0, width=2, height=1)]

        with pytest.raises(DuplicateDisplayNamesError) as excinfo:
            build_namenfit_rows(plan, "Vorname Nachname")
        assert excinfo.value.duplicates[0].display_name == "Anna Gold"
        assert excinfo.value.duplicates[0].count == 2

    def test_ungrouped_named_student_raises(self):
        """Direkter Test der Absicherung, da normalize_tablegroups() im Normalbetrieb
        jedem benannten Schueler (auch einzeln sitzenden) automatisch eine Gruppe zuweist --
        dieser Fehlerpfad greift nur, wenn diese Invariante je verletzt wird."""
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=5, y=5, first_name="Ben", last_name="Meier")
        plan = make_plan(students=[s1, s2])
        plan.tablegroups = [_rect_group(1, 0, 0, width=1, height=1)]  # Ben absichtlich nicht abgedeckt

        with pytest.raises(UngroupedStudentsError) as excinfo:
            _resolve_group_numbers(plan, [s1, s2])
        assert excinfo.value.offenders == [UngroupedStudent(display_name="Ben", x=5, y=5)]


class TestExportNamenfitCsv:
    def test_writes_utf8_comma_delimited_file(self, tmp_path):
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=1, y=0, first_name="Ben", last_name="Meier")
        plan = make_plan(students=[s1, s2])
        plan.tablegroups = [_rect_group(1, 0, 0, width=2, height=1)]

        output = tmp_path / "Testklasse.csv"
        export_namenfit_csv(plan, output, name_format="Vorname Nachname")

        with open(output, newline="", encoding="utf-8") as file_handle:
            rows = list(csv.reader(file_handle))
        assert rows == [["Tisch 1", ""], ["Anna Gold", "Ben Meier"]]

    def test_propagates_domain_errors(self, tmp_path):
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=1, y=0, first_name="Anna", last_name="Gold")
        plan = make_plan(students=[s1, s2])
        plan.tablegroups = [_rect_group(1, 0, 0, width=2, height=1)]

        with pytest.raises(DuplicateDisplayNamesError):
            export_namenfit_csv(plan, tmp_path / "out.csv", name_format="Vorname Nachname")
        assert not (tmp_path / "out.csv").exists()
