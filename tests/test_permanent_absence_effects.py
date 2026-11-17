"""Wirkung von "dauerhaft abwesend": Exporte, Abgaben zählen, Sperre für Einträge.

Synthetische Pläne (erfundene Namen); Dateien nur in ``tmp_path``.
"""

from __future__ import annotations

import zipfile

import pytest

from app.core.domain.namenfit_csv_export import build_namenfit_rows
from app.core.domain.permanent_absence import apply_export_visibility
from app.core.domain.seat_orientation import TEACHER_BOTTOM
from app.core.domain.submission_matching import match_submission_folders
from app.core.domain.table_groups import build_seat_geometries_v4
from app.core.usecases.v4.color_usecases import toggle_color_tag
from app.core.usecases.v4.grade_usecases import add_grade_column, record_grade
from app.core.usecases.v4.participation_usecases import set_participation_rating
from app.core.usecases.v4.submission_usecases import apply_missing_submissions
from app.core.usecases.v4.symbol_usecases import record_symbol, toggle_diagnostic_symbol
from app.core.usecases.v4.tablegroup_usecases import apply_normalized_tablegroups
from app.infrastructure.exporters.pdf_exporter import PdfSeatingPlanExporter
from tests.conftest import make_plan, make_student
from tests.test_submission_usecases import ABSENT, DATE, NAMES


@pytest.fixture
def class_plan():
    """Anna (1,0) + abwesende Ben (2,0) als Gruppe, abwesender Cem allein auf (5,5)."""
    anna = make_student(x=1, y=0, first_name="Anna", last_name="Alt")
    ben = make_student(x=2, y=0, first_name="Ben", last_name="Berg")
    cem = make_student(x=5, y=5, first_name="Cem", last_name="Cal")
    ben.permanently_absent = cem.permanently_absent = True
    plan = make_plan(students=[anna, ben, cem])
    apply_normalized_tablegroups(plan)
    return plan, anna, ben, cem


def test_export_geometries_empty_the_group_desk_and_drop_the_lone_desk(class_plan):
    plan, anna, ben, cem = class_plan
    shown = apply_export_visibility(plan, build_seat_geometries_v4(plan))
    seats = {(g.x, g.y): g.student for g in shown if not g.is_teacher}
    assert seats[(1, 0)] is not None and seats[(1, 0)].student_id == anna.student_id
    assert (2, 0) in seats and seats[(2, 0)] is None
    assert (5, 5) not in seats


def test_namenfit_csv_lists_only_present_students(class_plan):
    plan, *_ = class_plan
    cells = {cell for row in build_namenfit_rows(plan, "Vorname") for cell in row if cell}
    assert "Anna" in cells
    assert not {"Ben", "Cem"} & cells


def test_png_zip_has_cards_only_for_present_students(class_plan, tmp_path):
    pytest.importorskip("PIL")
    from app.infrastructure.exporters.student_png_zip_exporter import export_student_pngs_zip

    plan, *_ = class_plan
    out = tmp_path / "karten.zip"
    assert export_student_pngs_zip(plan, out) == 1
    assert zipfile.ZipFile(out).namelist() == ["Anna.png"]


def test_pdf_draws_no_absent_names_and_skips_the_lone_desk(class_plan, tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    plan, *_ = class_plan
    exporter = PdfSeatingPlanExporter(symbol_definitions=[])
    drawn: list = []
    monkeypatch.setattr(exporter._desk_renderer, "render_desk", lambda c, colors, pdfm, seat, *rest: drawn.append((seat, rest[-1])))
    exporter.export_plan(plan, tmp_path / "plan.pdf", TEACHER_BOTTOM)

    display_names = drawn[0][1]
    assert set(display_names.values()) == {"Anna Alt"}
    assert {(seat.x, seat.y) for seat, _names in drawn if not seat.is_teacher} == {(1, 0), (2, 0)}


def test_submission_matching_and_missing_marks_skip_absent_students(class_plan):
    plan, anna, ben, _cem = class_plan
    match = match_submission_folders(["Ben Berg"], plan.classroom.students)
    assert match.matched == {} and tuple(match.unknown) == ("Ben Berg",)

    result = apply_missing_submissions(plan, DATE, [], NAMES, absent_symbol=ABSENT, mark_absent=True, mode="replace")
    session = result.documentation.session_for_date(DATE)
    assert session.entry_for(anna.student_id).symbols
    assert session.entry_for(ben.student_id) is None or not session.entry_for(ben.student_id).symbols


def test_entries_for_absent_students_are_locked(class_plan):
    plan, _anna, ben, _cem = class_plan
    sid = ben.student_id
    plan, column = add_grade_column(plan, "schriftlich", "KA 1")

    assert record_grade(plan, sid, column, 2.0).documentation.grade_of(sid, column) is None
    assert toggle_color_tag(plan, sid, "gelb").student_by_id(sid).diagnostic.color_tags == []
    assert toggle_diagnostic_symbol(plan, sid, DATE, "Beteiligung").student_by_id(sid).diagnostic.symbols == {}
    for changed in (record_symbol(plan, sid, DATE, ABSENT, 1), set_participation_rating(plan, sid, DATE, "+")):
        session = changed.documentation.session_for_date(DATE)
        entry = session.entry_for(sid) if session else None
        assert entry is None or not entry.has_content()


def test_unmarking_unlocks_again(class_plan):
    plan, _anna, ben, _cem = class_plan
    ben_plan = plan
    ben_plan.student_by_id(ben.student_id).permanently_absent = False
    assert toggle_color_tag(ben_plan, ben.student_id, "gelb").student_by_id(ben.student_id).diagnostic.color_tags == ["gelb"]


def test_empty_desks_keep_their_previous_rules():
    """Die Sperre gilt nur für dauerhaft Abwesende: Farbpunkte an leeren Tischen bleiben wie bisher möglich."""
    empty = make_student(x=1, y=0, first_name="")
    plan = make_plan(students=[empty])
    assert toggle_color_tag(plan, empty.student_id, "gelb").student_by_id(empty.student_id).diagnostic.color_tags == ["gelb"]
