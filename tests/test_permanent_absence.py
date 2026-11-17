"""Tests für "dauerhaft abwesend": Regelmodul, Usecase, Persistenz, Undo.

Synthetische Pläne aus ``tests/conftest.py`` (erfundene Namen).
"""

from __future__ import annotations

from app.application.app_state import AppState
from app.application.handlers.edit_handlers import handle_undo
from app.application.handlers.plan_handlers import handle_open_plan
from app.application.handlers.student_handlers import handle_rename_student, handle_set_permanently_absent
from app.core.domain.models_v4 import DiagnosticProfile
from app.core.domain.permanent_absence import (
    absent_student_ids,
    accepts_entries,
    accepts_notes,
    active_students,
    export_seat_visibility,
    is_active,
)
from app.core.intents.edit_intents import UndoIntent
from app.core.intents.plan_intents import OpenPlanIntent
from app.core.intents.student_intents import RenameStudentIntent, SetPermanentlyAbsentIntent
from app.core.usecases.v4.grade_usecases import add_grade_column
from app.core.usecases.v4.student_usecases import drop_unnamed_desk_data, set_permanently_absent
from app.core.usecases.v4.symbol_usecases import record_symbol
from app.core.usecases.v4.tablegroup_usecases import apply_normalized_tablegroups
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan
from tests.conftest import make_plan, make_student
from tests.test_app_controller import PLANS_DIR, make_ctx


def _absent(student):
    student.permanently_absent = True
    return student


def test_predicates() -> None:
    present, absent, empty = make_student(), _absent(make_student(first_name="Ben")), make_student(first_name="", last_name="")
    assert is_active(present) and accepts_entries(present)
    assert not is_active(absent) and not accepts_entries(absent)
    assert not is_active(empty)
    assert not accepts_entries(empty) and not accepts_notes(empty)  # Personendaten nur für Schüler:innen
    assert accepts_notes(absent)  # Notizen bleiben für dauerhaft Abwesende bearbeitbar
    assert active_students([present, absent, empty]) == [present]
    assert absent_student_ids([present, absent, empty]) == {absent.student_id}


def test_absent_desk_in_a_group_with_shown_desks_is_emptied_otherwise_hidden() -> None:
    """Gruppe A: (1,0)+(2,0), eine Person abwesend -> leer. Einzeltisch (5,5) abwesend -> weg.
    Gruppe B: (1,3)+(2,3), beide abwesend -> beide weg."""
    in_group = _absent(make_student(x=1, y=0))
    neighbour = make_student(x=2, y=0, first_name="Ben")
    alone = _absent(make_student(x=5, y=5, first_name="Cem"))
    pair = [_absent(make_student(x=1, y=3, first_name="Dana")), _absent(make_student(x=2, y=3, first_name="Eli"))]
    plan = make_plan(students=[in_group, neighbour, alone, *pair])
    apply_normalized_tablegroups(plan)

    visibility = export_seat_visibility(plan)

    assert visibility.emptied == {in_group.student_id}
    assert visibility.hidden == {alone.student_id, *(s.student_id for s in pair)}


def test_empty_desk_in_the_group_counts_as_shown() -> None:
    absent = _absent(make_student(x=1, y=0))
    plan = make_plan(students=[absent, make_student(x=2, y=0, first_name="", last_name="")])
    apply_normalized_tablegroups(plan)
    assert export_seat_visibility(plan).emptied == {absent.student_id}


def test_usecase_marks_and_unmarks_but_never_an_unnamed_desk() -> None:
    named, empty = make_student(), make_student(x=3, first_name="", last_name="")
    plan = make_plan(students=[named, empty])

    marked = set_permanently_absent(plan, named.student_id, True)
    assert marked.student_by_id(named.student_id).permanently_absent
    assert not plan.student_by_id(named.student_id).permanently_absent  # Kopie
    assert not set_permanently_absent(marked, named.student_id, False).student_by_id(named.student_id).permanently_absent
    assert not set_permanently_absent(plan, empty.student_id, True).student_by_id(empty.student_id).permanently_absent


def _with_person_data(student):
    """Gibt *student* Farbpunkt, Notiz, Diagnosesymbol und Abwesend-Markierung."""
    student.diagnostic.color_tags = ["gelb"]
    student.diagnostic.notes = ["Absprache"]
    student.diagnostic.symbols = {"Beteiligung": 2}
    return _absent(student)


def test_invariant_drops_all_person_data_of_unnamed_desks() -> None:
    named = _with_person_data(make_student(x=1, first_name="Anna"))
    empty = _with_person_data(make_student(x=2, first_name="Ben"))
    empty.permanently_absent = False  # Eintragen erst erlauben, Altdaten wie aus einer alten Datei
    plan = record_symbol(make_plan(students=[named, empty]), empty.student_id, "2026-11-17", "Abwesend", 1)
    plan, column = add_grade_column(plan, "schriftlich", "KA")
    plan.documentation.set_grade(empty.student_id, column, 2.0)
    assert any(empty.student_id in session.entries for session in plan.documentation.sessions)
    plan.student_by_id(empty.student_id).first_name_official = ""  # Name weg, Daten noch da
    plan.student_by_id(empty.student_id).last_name = ""
    plan.student_by_id(empty.student_id).permanently_absent = True

    drop_unnamed_desk_data(plan)

    cleared = plan.student_by_id(empty.student_id)
    assert cleared.diagnostic == DiagnosticProfile() and not cleared.permanently_absent
    assert all(empty.student_id not in session.entries for session in plan.documentation.sessions)
    assert plan.documentation.grade_of(empty.student_id, column) is None
    kept = plan.student_by_id(named.student_id)
    assert kept.diagnostic.notes == ["Absprache"] and kept.permanently_absent


def test_removing_the_name_drops_the_data_and_undo_restores_it() -> None:
    student = _with_person_data(make_student(first_name="Anna", nickname=""))
    plan = make_plan(students=[student])
    path = PLANS_DIR / "test.json"
    ctx = make_ctx({path: plan})
    state = handle_open_plan(OpenPlanIntent(plan_path=path), AppState(), ctx)

    state = handle_rename_student(RenameStudentIntent(student_id=student.student_id, first_name="", last_name=""), state, ctx)
    assert state.current_plan.student_by_id(student.student_id).diagnostic == DiagnosticProfile()

    state = handle_undo(UndoIntent(), state, ctx)
    restored = state.current_plan.student_by_id(student.student_id)
    assert restored.diagnostic.notes == ["Absprache"] and restored.permanently_absent


def test_opening_a_plan_cleans_old_data_at_empty_desks() -> None:
    empty = _with_person_data(make_student(first_name="", last_name=""))
    plan = make_plan(students=[empty])
    path = PLANS_DIR / "alt.json"
    state = handle_open_plan(OpenPlanIntent(plan_path=path), AppState(), make_ctx({path: plan}))
    assert state.current_plan.student_by_id(empty.student_id).diagnostic == DiagnosticProfile()


def test_roundtrip_writes_the_key_only_when_set() -> None:
    absent, present = _absent(make_student()), make_student(x=2, first_name="Ben")
    payload = serialize_plan(make_plan(students=[absent, present]))
    raw = {s["student_id"]: s for s in payload["classroom"]["students"]}
    assert raw[str(absent.student_id)]["permanently_absent"] is True
    assert "permanently_absent" not in raw[str(present.student_id)]
    restored = deserialize_plan(payload)
    assert restored.student_by_id(absent.student_id).permanently_absent
    assert not restored.student_by_id(present.student_id).permanently_absent


def test_handler_is_one_undo_step() -> None:
    student = make_student()
    plan = make_plan(students=[student])
    path = PLANS_DIR / "test.json"
    ctx = make_ctx({path: plan})
    opened = handle_open_plan(OpenPlanIntent(plan_path=path), AppState(), ctx)  # zeichnet den Ausgangsstand auf
    state = handle_set_permanently_absent(SetPermanentlyAbsentIntent(student_id=student.student_id, absent=True), opened, ctx)
    assert state.current_plan.student_by_id(student.student_id).permanently_absent
    state = handle_undo(UndoIntent(), state, ctx)
    assert not state.current_plan.student_by_id(student.student_id).permanently_absent
