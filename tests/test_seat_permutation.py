"""Fachsemantik-Tests für ``resolve_cut_paste_moves`` (T4-Ergänzung).

Testet die reine Permutations-Logik isoliert von ``StudentClipboard`` und
``SeatingPlan`` — nur mit einem minimalen ``Classroom``-Setup.
"""

from __future__ import annotations

from app.core.domain.models_v4 import Classroom, TeacherSeat
from app.core.domain.seat_permutation import SeatMove, resolve_cut_paste_moves
from tests.conftest import make_student


class TestSingleSwap:
    def test_single_cut_student_swaps_with_foreign_occupant(self):
        """Ein einzelner ausgeschnittener Tisch tauscht mit dem Tisch am Ziel."""
        anna = make_student(x=1, y=0)
        ben = make_student(x=3, y=0)
        classroom = Classroom(teacher_seat=TeacherSeat(x=0, y=0), students=[anna, ben])

        moves = resolve_cut_paste_moves(
            classroom, batch_moves=[(anna.student_id, (1, 0), (3, 0))]
        )

        assert moves == [
            SeatMove(anna.student_id, (1, 0), (3, 0)),
            SeatMove(ben.student_id, (3, 0), (1, 0)),
        ]

    def test_empty_target_produces_no_extra_move(self):
        """Ist das Ziel unbesetzt, entsteht keine zusätzliche Verdrängungsbewegung."""
        anna = make_student(x=1, y=0)
        classroom = Classroom(teacher_seat=TeacherSeat(x=0, y=0), students=[anna])

        moves = resolve_cut_paste_moves(
            classroom, batch_moves=[(anna.student_id, (1, 0), (3, 0))]
        )

        assert moves == [SeatMove(anna.student_id, (1, 0), (3, 0))]


class TestBatchInternalCircle:
    def test_two_batch_students_swapping_directly_produce_no_foreign_move(self):
        """Tauschen zwei Batch-Tische direkt untereinander, ist niemand fremd betroffen."""
        anna = make_student(x=0, y=0)
        ben = make_student(x=1, y=0)
        classroom = Classroom(teacher_seat=TeacherSeat(x=0, y=0), students=[anna, ben])

        moves = resolve_cut_paste_moves(
            classroom,
            batch_moves=[
                (anna.student_id, (0, 0), (1, 0)),
                (ben.student_id, (1, 0), (0, 0)),
            ],
        )

        assert moves == [
            SeatMove(anna.student_id, (0, 0), (1, 0)),
            SeatMove(ben.student_id, (1, 0), (0, 0)),
        ]


class TestChainedDisplacement:
    def test_foreign_occupant_follows_chain_to_its_actual_end(self):
        """Der verdrängte Fremde landet am tatsächlichen Kettenende, nicht auf dem
        blockierten Zwischenplatz, den ein zweiter Batch-Tisch beansprucht."""
        anna = make_student(x=3, y=0)
        ben = make_student(x=3, y=1)
        foreigner = make_student(x=3, y=-1)
        classroom = Classroom(
            teacher_seat=TeacherSeat(x=0, y=0), students=[anna, ben, foreigner]
        )

        moves = resolve_cut_paste_moves(
            classroom,
            batch_moves=[
                (anna.student_id, (3, 0), (3, -1)),
                (ben.student_id, (3, 1), (3, 0)),
            ],
        )

        assert moves == [
            SeatMove(anna.student_id, (3, 0), (3, -1)),
            SeatMove(ben.student_id, (3, 1), (3, 0)),
            SeatMove(foreigner.student_id, (3, -1), (3, 1)),
        ]

    def test_two_independent_chains_in_same_selection_do_not_interfere(self):
        """Zwei unabhängige Verdrängungen in derselben Auswahl bleiben getrennt."""
        anna = make_student(x=0, y=0)
        foreign_a = make_student(x=10, y=0)
        clara = make_student(x=0, y=5)
        foreign_c = make_student(x=10, y=5)
        classroom = Classroom(
            teacher_seat=TeacherSeat(x=0, y=0),
            students=[anna, foreign_a, clara, foreign_c],
        )

        moves = resolve_cut_paste_moves(
            classroom,
            batch_moves=[
                (anna.student_id, (0, 0), (10, 0)),
                (clara.student_id, (0, 5), (10, 5)),
            ],
        )

        assert moves == [
            SeatMove(anna.student_id, (0, 0), (10, 0)),
            SeatMove(clara.student_id, (0, 5), (10, 5)),
            SeatMove(foreign_a.student_id, (10, 0), (0, 0)),
            SeatMove(foreign_c.student_id, (10, 5), (0, 5)),
        ]


class TestInvariantUninvolvedStudentsUntouched:
    def test_students_outside_batch_and_displaced_chain_are_never_moved(self):
        """Unbeteiligte Tische außerhalb von Auswahl und Verdrängungskette bleiben
        garantiert unangetastet — kein unkontrollierter Dominoeffekt."""
        anna = make_student(x=1, y=0)
        ben = make_student(x=3, y=0)
        bystander = make_student(x=20, y=20)
        classroom = Classroom(
            teacher_seat=TeacherSeat(x=0, y=0), students=[anna, ben, bystander]
        )

        moves = resolve_cut_paste_moves(
            classroom, batch_moves=[(anna.student_id, (1, 0), (3, 0))]
        )

        moved_ids = {move.student_id for move in moves}
        assert bystander.student_id not in moved_ids
