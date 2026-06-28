"""Tests für v4 accommodation_usecases."""

from app.core.domain.student_id import StudentId
from app.core.usecases.v4.accommodation_usecases import set_accommodations
from tests.conftest import make_plan, make_student


class TestSetAccommodations:
    def test_sets_list(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id)])
        result = set_accommodations(plan, anna_id, ["Zeitzuschlag 25 %", "Nutzung Laptop"])
        s = result.student_by_id(anna_id)
        assert s.diagnostic.accommodations == ["Zeitzuschlag 25 %", "Nutzung Laptop"]

    def test_trims_and_filters_empty_entries(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id)])
        result = set_accommodations(plan, anna_id, ["  Zeitzuschlag 25 %  ", "   ", "", "Laptop"])
        s = result.student_by_id(anna_id)
        assert s.diagnostic.accommodations == ["Zeitzuschlag 25 %", "Laptop"]

    def test_replaces_existing_list(self, anna_id):
        student = make_student(student_id=anna_id)
        student.diagnostic.accommodations = ["Alt"]
        plan = make_plan(students=[student])
        result = set_accommodations(plan, anna_id, ["Neu"])
        s = result.student_by_id(anna_id)
        assert s.diagnostic.accommodations == ["Neu"]

    def test_no_effect_for_unknown_id(self, plan_with_anna):
        result = set_accommodations(plan_with_anna, StudentId.new(), ["X"])
        assert len(result.classroom.students) == 1
        assert result.classroom.students[0].diagnostic.accommodations == []
