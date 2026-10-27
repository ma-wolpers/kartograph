"""Tests für die Invariante "gespeicherte Tischgruppen passen zur Sitznachbarschaft".

Abgesichert sind die rein lesende Berechnung (``compute_normalized_tablegroups``),
das Durchsetzen beim Übernehmen jedes Planzustands (``_record_and_save``,
gezeigt am Umsetzen eines Tisches über den echten Move-Handler) und beim Öffnen
einer Plandatei (``handle_open_plan``). Nur synthetische Daten.
"""

from __future__ import annotations

from app.application.app_state import AppState
from app.application.handlers.plan_handlers import handle_open_plan
from app.application.handlers.student_handlers import handle_move_student
from app.core.domain.models_v4 import GroupSeat, TableGroup
from app.core.intents.plan_intents import OpenPlanIntent
from app.core.intents.student_intents import MoveStudentIntent
from app.core.usecases.v4.tablegroup_usecases import compute_normalized_tablegroups
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan
from tests.conftest import make_plan, make_student
from tests.test_app_controller import PLANS_DIR, FakePlanRepository
from tests.test_plan_save_debounce import _make_ctx


def _rotated_pair_plan_with_loner():
    """Plan: Gruppe 1 auf (1,2)+(2,2), 15° gedreht; einzelner Tisch auf (5,5) ohne Gruppe.

    Returns:
        ``(plan, loner)``, wobei ``loner`` der Schüler auf (5,5) ist.
    """
    loner = make_student(x=5, y=5, first_name="Lia")
    plan = make_plan(students=[
        make_student(x=1, y=2, first_name="Ada"),
        make_student(x=2, y=2, first_name="Ben"),
        loner,
    ])
    plan.tablegroups = [TableGroup(group_id=1, seats=[
        GroupSeat(x=1, y=2, rotation=15.0),
        GroupSeat(x=2, y=2, rotation=15.0),
    ])]
    return plan, loner


def _seat_rotation(groups: list[TableGroup], x: int, y: int) -> float | None:
    """Rotation des Gruppenplatzes (x, y), ``None`` wenn der Platz zu keiner Gruppe gehört."""
    for group in groups:
        for seat in group.seats:
            if (seat.x, seat.y) == (x, y):
                return seat.rotation
    return None


def test_seat_adjacent_to_rotated_group_adopts_its_rotation() -> None:
    """Ein angesetzter Tisch wird Teil der Gruppe und übernimmt deren Drehung."""
    plan, loner = _rotated_pair_plan_with_loner()
    loner.seat.x, loner.seat.y = 3, 2

    groups = compute_normalized_tablegroups(plan)

    assert _seat_rotation(groups, 3, 2) == 15.0


def test_component_without_named_student_forms_no_group() -> None:
    """Ein Block nur aus unbenannten Plätzen bildet keine Gruppe."""
    plan = make_plan(students=[make_student(x=4, y=4, first_name="", last_name="")])

    assert compute_normalized_tablegroups(plan) == []


def test_compute_does_not_mutate_plan_and_is_idempotent() -> None:
    """Die Berechnung liest nur; erneutes Anwenden ändert nichts mehr."""
    plan, _loner = _rotated_pair_plan_with_loner()
    before = [(g.group_id, [(s.x, s.y, s.rotation) for s in g.seats]) for g in plan.tablegroups]

    first = compute_normalized_tablegroups(plan)
    assert [(g.group_id, [(s.x, s.y, s.rotation) for s in g.seats]) for g in plan.tablegroups] == before

    plan.tablegroups = first
    assert compute_normalized_tablegroups(plan) == first


def test_move_handler_commits_normalized_tablegroups() -> None:
    """Umsetzen neben eine gedrehte Gruppe: der übernommene Zustand trägt sofort deren Drehung."""
    plan, loner = _rotated_pair_plan_with_loner()
    state = AppState(current_plan=plan, current_plan_path=PLANS_DIR / "x.json")

    new_state = handle_move_student(
        MoveStudentIntent(student_id=loner.student_id, new_x=3, new_y=2), state, _make_ctx()
    )

    assert _seat_rotation(new_state.current_plan.tablegroups, 3, 2) == 15.0


def test_opening_a_file_with_stale_groups_normalizes_them() -> None:
    """Eine Datei, deren Gruppen nicht zur Sitznachbarschaft passen, wird beim Öffnen korrigiert.

    Das Repository selbst bleibt ein treuer Spiegel (veraltete Gruppen kommen
    unverändert aus ``deserialize_plan``), erst ``handle_open_plan`` normalisiert.
    """
    plan, loner = _rotated_pair_plan_with_loner()
    loner.seat.x, loner.seat.y = 3, 2  # veraltet: (3,2) steht in keiner gespeicherten Gruppe
    stored = deserialize_plan(serialize_plan(plan))
    assert _seat_rotation(stored.tablegroups, 3, 2) is None
    path = PLANS_DIR / "stale.json"
    ctx = _make_ctx(FakePlanRepository(plans={path: stored}))

    new_state = handle_open_plan(OpenPlanIntent(plan_path=path), AppState(), ctx)

    assert _seat_rotation(new_state.current_plan.tablegroups, 3, 2) == 15.0
