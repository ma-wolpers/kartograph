"""Tests für "dauerhaft abwesend": Regelmodul, Usecase, Persistenz, Undo.

Synthetische Pläne aus ``tests/conftest.py`` (erfundene Namen).
"""

from __future__ import annotations

from app.application.app_state import AppState
from app.application.handlers.edit_handlers import handle_undo
from app.application.handlers.plan_handlers import handle_open_plan
from app.application.handlers.student_handlers import handle_set_permanently_absent
from app.core.domain.permanent_absence import (
    absent_student_ids,
    accepts_entries,
    active_students,
    export_seat_visibility,
    is_active,
)
from app.core.intents.edit_intents import UndoIntent
from app.core.intents.plan_intents import OpenPlanIntent
from app.core.intents.student_intents import SetPermanentlyAbsentIntent
from app.core.usecases.v4.student_usecases import rename_student, set_nickname, set_permanently_absent
from app.core.usecases.v4.tablegroup_usecases import apply_normalized_tablegroups
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan
from tests.conftest import make_plan, make_student
from tests.test_app_controller import PLANS_DIR, make_ctx


def _absent(student):
    student.permanently_absent = True
    return student


def test_predicates() -> None:
    present, absent, empty = make_student(), _absent(make_student(first_name="Ben")), make_student(first_name="")
    assert is_active(present) and accepts_entries(present)
    assert not is_active(absent) and not accepts_entries(absent)
    assert not is_active(empty)
    assert accepts_entries(empty)  # leere Tische regelt weiter is_named(), nicht die Abwesenheits-Sperre
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
    plan = make_plan(students=[absent, make_student(x=2, y=0, first_name="")])
    apply_normalized_tablegroups(plan)
    assert export_seat_visibility(plan).emptied == {absent.student_id}


def test_usecase_marks_and_unmarks_but_never_an_unnamed_desk() -> None:
    named, empty = make_student(), make_student(x=3, first_name="")
    plan = make_plan(students=[named, empty])

    marked = set_permanently_absent(plan, named.student_id, True)
    assert marked.student_by_id(named.student_id).permanently_absent
    assert not plan.student_by_id(named.student_id).permanently_absent  # Kopie
    assert not set_permanently_absent(marked, named.student_id, False).student_by_id(named.student_id).permanently_absent
    assert not set_permanently_absent(plan, empty.student_id, True).student_by_id(empty.student_id).permanently_absent


def test_removing_the_name_removes_the_mark() -> None:
    student = _absent(make_student(first_name="Anna", nickname=""))
    plan = make_plan(students=[student])
    assert not rename_student(plan, student.student_id, "", "").student_by_id(student.student_id).permanently_absent
    kept = set_nickname(plan, student.student_id, "Anni")
    assert kept.student_by_id(student.student_id).permanently_absent


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
