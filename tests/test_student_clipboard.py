"""Tests für die v4-native Schüler-Zwischenablage (StudentClipboard, T4)."""

from __future__ import annotations

import pytest

from app.core.domain.models_v4 import (
    DiagnosticProfile,
    GroupSeat,
    Session,
    SessionEntry,
    TableGroup,
    TeacherSeat,
)
from app.core.domain.student_clipboard import StudentClipboard
from app.core.domain.student_id import StudentId
from tests.conftest import make_plan, make_student


# ---------------------------------------------------------------------------
# copy_from_plan / mark_for_cut: reine Erfassung, kein Plan-Effekt
# ---------------------------------------------------------------------------

class TestCopyAndCutDoNotMutatePlan:
    def test_copy_from_plan_does_not_change_plan(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        clip = StudentClipboard()

        count = clip.copy_from_plan(plan, [(1, 0)])

        assert count == 1
        assert plan.classroom.student_at(1, 0) is not None

    def test_mark_for_cut_does_not_remove_student(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        clip = StudentClipboard()

        count = clip.mark_for_cut(plan, [(1, 0)])

        assert count == 1
        assert plan.classroom.student_at(1, 0) is not None
        assert plan.classroom.student_by_id(anna.student_id) is not None

    def test_cells_without_student_are_ignored(self):
        plan = make_plan()
        clip = StudentClipboard()

        count = clip.copy_from_plan(plan, [(5, 5), (6, 6)])

        assert count == 0
        assert clip.has_content() is False

    def test_has_content_reflects_buffer_state(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        clip = StudentClipboard()
        assert clip.has_content() is False

        clip.copy_from_plan(plan, [(1, 0)])
        assert clip.has_content() is True

        clip.clear()
        assert clip.has_content() is False


# ---------------------------------------------------------------------------
# Einfügen nach Kopieren: frische StudentId, keine Dokuhistorie
# ---------------------------------------------------------------------------

class TestPasteAfterCopy:
    def test_paste_creates_clone_with_new_id_at_target(self):
        anna = make_student(x=1, y=0, first_name="Anna", last_name="Müller")
        plan = make_plan(students=[anna])
        clip = StudentClipboard()
        clip.copy_from_plan(plan, [(1, 0)])

        next_plan, pasted, teacher_conflict = clip.paste_into_plan(plan, target_x=3, target_y=0)

        assert pasted == 1
        assert teacher_conflict is False
        clone = next_plan.classroom.student_at(3, 0)
        assert clone is not None
        assert clone.student_id != anna.student_id
        assert clone.first_name == "Anna"
        assert clone.last_name == "Müller"
        assert clone.first_name_official == "Anna"
        # Original bleibt unveraendert an seinem Platz stehen.
        assert next_plan.classroom.student_at(1, 0) is not None
        assert next_plan.classroom.student_at(1, 0).student_id == anna.student_id

    def test_paste_copies_nickname(self):
        anna = make_student(x=1, y=0, first_name="Alexander", nickname="Alex")
        plan = make_plan(students=[anna])
        clip = StudentClipboard()
        clip.copy_from_plan(plan, [(1, 0)])

        next_plan, _pasted, _conflict = clip.paste_into_plan(plan, target_x=3, target_y=0)

        clone = next_plan.classroom.student_at(3, 0)
        assert clone.nickname == "Alex"
        assert clone.first_name == "Alex"

    def test_paste_copies_diagnostic_profile_but_not_session_history(self):
        anna = make_student(x=1, y=0)
        anna.diagnostic = DiagnosticProfile(symbols={"Laptop": 2}, color_tags=["gelb"])
        plan = make_plan(students=[anna])
        plan.documentation.sessions.append(
            Session(date="2025-09-01", entries={anna.student_id: SessionEntry(note="Testnotiz")})
        )
        clip = StudentClipboard()
        clip.copy_from_plan(plan, [(1, 0)])

        next_plan, pasted, _ = clip.paste_into_plan(plan, target_x=3, target_y=0)

        clone = next_plan.classroom.student_at(3, 0)
        assert pasted == 1
        assert clone.diagnostic.symbols == {"Laptop": 2}
        assert clone.diagnostic.color_tags == ["gelb"]
        # Diagnoseprofil ist eine Kopie, keine geteilte Referenz.
        clone.diagnostic.symbols["Laptop"] = 99
        assert anna.diagnostic.symbols["Laptop"] == 2
        # Dokuhistorie bleibt beim Original (Sessions sind ID-indiziert).
        session = next_plan.documentation.session_for_date("2025-09-01")
        assert session.entry_for(clone.student_id) is None
        assert session.entry_for(anna.student_id) is not None

    def test_paste_can_be_repeated_with_distinct_ids(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        clip = StudentClipboard()
        clip.copy_from_plan(plan, [(1, 0)])

        plan_after_first, _, _ = clip.paste_into_plan(plan, target_x=3, target_y=0)
        plan_after_second, _, _ = clip.paste_into_plan(plan_after_first, target_x=4, target_y=0)

        ids = {s.student_id for s in plan_after_second.classroom.students}
        assert len(ids) == 3

    def test_paste_blocked_by_teacher_seat_reports_conflict(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        clip = StudentClipboard()
        clip.copy_from_plan(plan, [(1, 0)])

        next_plan, pasted, teacher_conflict = clip.paste_into_plan(plan, target_x=0, target_y=0)

        assert pasted == 0
        assert teacher_conflict is True
        assert next_plan.classroom.student_at(0, 0) is None

    def test_paste_overwrites_foreign_occupant_and_purges_its_history(self):
        anna = make_student(x=1, y=0, student_id=StudentId.new())
        ben = make_student(x=3, y=0, student_id=StudentId.new())
        plan = make_plan(students=[anna, ben])
        plan.documentation.sessions.append(
            Session(date="2025-09-01", entries={ben.student_id: SessionEntry(note="Ben war da")})
        )
        clip = StudentClipboard()
        clip.copy_from_plan(plan, [(1, 0)])

        next_plan, pasted, _ = clip.paste_into_plan(plan, target_x=3, target_y=0)

        assert pasted == 1
        assert next_plan.classroom.student_by_id(ben.student_id) is None
        session = next_plan.documentation.session_for_date("2025-09-01")
        assert session.entry_for(ben.student_id) is None

    def test_paste_skips_entry_blocked_by_self_overlap(self):
        anna = make_student(x=0, y=0)
        ben = make_student(x=1, y=0)
        plan = make_plan(students=[anna, ben])
        clip = StudentClipboard()
        clip.copy_from_plan(plan, [(0, 0), (1, 0)])

        # Verschiebung um +1 in x: Annas Kopie zielt auf Bens (noch
        # unveraendertem) Originalplatz -> dieser einzelne Eintrag wird
        # uebersprungen statt Bens Daten zu ueberschreiben.
        next_plan, pasted, _ = clip.paste_into_plan(plan, target_x=1, target_y=0)

        assert pasted == 1
        ben_at_original = next_plan.classroom.student_at(1, 0)
        assert ben_at_original is not None
        assert ben_at_original.student_id == ben.student_id


# ---------------------------------------------------------------------------
# Einfügen nach Ausschneiden: ID/Historie bleibt erhalten, echte Verschiebung
# ---------------------------------------------------------------------------

class TestPasteAfterCut:
    def test_paste_moves_student_keeping_same_id(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        clip = StudentClipboard()
        clip.mark_for_cut(plan, [(1, 0)])

        next_plan, pasted, teacher_conflict = clip.paste_into_plan(plan, target_x=3, target_y=0)

        assert pasted == 1
        assert teacher_conflict is False
        assert next_plan.classroom.student_at(1, 0) is None
        moved = next_plan.classroom.student_at(3, 0)
        assert moved is not None
        assert moved.student_id == anna.student_id

    def test_paste_after_cut_preserves_session_history(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        plan.documentation.sessions.append(
            Session(date="2025-09-01", entries={anna.student_id: SessionEntry(note="Wichtige Notiz")})
        )
        clip = StudentClipboard()
        clip.mark_for_cut(plan, [(1, 0)])

        next_plan, pasted, _ = clip.paste_into_plan(plan, target_x=3, target_y=0)

        assert pasted == 1
        session = next_plan.documentation.session_for_date("2025-09-01")
        assert session.entry_for(anna.student_id).note == "Wichtige Notiz"

    def test_paste_after_cut_migrates_tablegroup_membership(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        plan.tablegroups.append(
            TableGroup(group_id=1, seats=[GroupSeat(x=1, y=0, shift_x=0.05, rotation=2.5)])
        )
        clip = StudentClipboard()
        clip.mark_for_cut(plan, [(1, 0)])

        next_plan, pasted, _ = clip.paste_into_plan(plan, target_x=3, target_y=0)

        assert pasted == 1
        seat = next_plan.tablegroups[0].seats[0]
        assert (seat.x, seat.y) == (3, 0)
        assert seat.shift_x == pytest.approx(0.05)
        assert seat.rotation == pytest.approx(2.5)

    def test_paste_can_be_repeated_moving_same_student_again(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        clip = StudentClipboard()
        clip.mark_for_cut(plan, [(1, 0)])

        plan_after_first, pasted1, _ = clip.paste_into_plan(plan, target_x=3, target_y=0)
        plan_after_second, pasted2, _ = clip.paste_into_plan(plan_after_first, target_x=5, target_y=0)

        assert pasted1 == 1
        assert pasted2 == 1
        ids = {s.student_id for s in plan_after_second.classroom.students}
        assert ids == {anna.student_id}
        assert plan_after_second.classroom.student_at(5, 0) is not None

    def test_paste_skips_entry_deleted_after_cut(self):
        anna = make_student(x=1, y=0)
        plan = make_plan(students=[anna])
        clip = StudentClipboard()
        clip.mark_for_cut(plan, [(1, 0)])

        plan_without_anna = make_plan(students=[])

        next_plan, pasted, teacher_conflict = clip.paste_into_plan(plan_without_anna, target_x=3, target_y=0)

        assert pasted == 0
        assert teacher_conflict is False

    def test_paste_after_cut_overwrites_foreign_occupant(self):
        anna = make_student(x=1, y=0)
        ben = make_student(x=3, y=0)
        plan = make_plan(students=[anna, ben])
        clip = StudentClipboard()
        clip.mark_for_cut(plan, [(1, 0)])

        next_plan, pasted, _ = clip.paste_into_plan(plan, target_x=3, target_y=0)

        assert pasted == 1
        assert next_plan.classroom.student_by_id(ben.student_id) is None
        moved = next_plan.classroom.student_at(3, 0)
        assert moved.student_id == anna.student_id

    def test_paste_after_cut_swap_does_not_alias_tablegroup_seats(self):
        anna = make_student(x=0, y=0)
        ben = make_student(x=1, y=0)
        plan = make_plan(students=[anna, ben])
        plan.tablegroups.append(
            TableGroup(
                group_id=1,
                seats=[GroupSeat(x=0, y=0, shift_x=0.1), GroupSeat(x=1, y=0, shift_x=0.2)],
            )
        )
        clip = StudentClipboard()
        clip.mark_for_cut(plan, [(0, 0), (1, 0)])

        # Exakter Platztausch: Anna -> (1,0), Ben (relativ) -> (2,0).
        next_plan, pasted, _ = clip.paste_into_plan(plan, target_x=1, target_y=0)

        assert pasted == 2
        anna_seat = next_plan.classroom.student_by_id(anna.student_id).seat
        ben_seat = next_plan.classroom.student_by_id(ben.student_id).seat
        assert (anna_seat.x, anna_seat.y) == (1, 0)
        assert (ben_seat.x, ben_seat.y) == (2, 0)

        coords_with_shift = {(s.x, s.y): s.shift_x for s in next_plan.tablegroups[0].seats}
        assert coords_with_shift[(1, 0)] == pytest.approx(0.1)
        assert coords_with_shift[(2, 0)] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Multi-Zell-Selektion: relativer Versatz bleibt erhalten
# ---------------------------------------------------------------------------

class TestMultiCellOffsets:
    def test_copy_preserves_relative_offsets_on_paste(self):
        anna = make_student(x=0, y=0)
        ben = make_student(x=2, y=1)
        plan = make_plan(students=[anna, ben])
        clip = StudentClipboard()
        clip.copy_from_plan(plan, [(0, 0), (2, 1)])

        next_plan, pasted, _ = clip.paste_into_plan(plan, target_x=5, target_y=5)

        assert pasted == 2
        assert next_plan.classroom.student_at(5, 5) is not None
        assert next_plan.classroom.student_at(7, 6) is not None

    def test_empty_clipboard_paste_is_noop(self):
        plan = make_plan()
        clip = StudentClipboard()

        next_plan, pasted, teacher_conflict = clip.paste_into_plan(plan, target_x=1, target_y=1)

        assert pasted == 0
        assert teacher_conflict is False
        assert next_plan is plan
