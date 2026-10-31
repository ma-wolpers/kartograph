"""Eine Note je Person und Spalte: Modell, Altformat-Übernahme, Sicherung, Unabhängigkeit von Sessions."""

import json

import pytest

from app.core.domain.grade_scale import SCALE_POINTS_0_15
from app.core.domain.models_v4 import GradeConflict, Session, SessionEntry
from app.core.domain.student_id import StudentId
from app.core.usecases.v4.grade_scale_usecases import count_grades, set_grade_scale
from app.core.usecases.v4.grade_usecases import add_grade_column, record_grade, resolve_grade_conflicts
from app.core.usecases.v4.session_usecases import rename_session_date
from app.core.usecases.v4.student_usecases import delete_student
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan
from app.infrastructure.repositories.v4.grade_store_codec import has_legacy_session_grades
from app.infrastructure.repositories.v4.json_plan_repository_v4 import (
    LEGACY_GRADES_BACKUP_LABEL,
    JsonSeatingPlanRepositoryV4,
)
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan
from tests.conftest import make_plan, make_student


@pytest.fixture
def graded():
    sid = StudentId.new()
    plan, col = add_grade_column(make_plan(students=[make_student(student_id=sid)]), "schriftlich", "Arbeit")
    return plan, sid, col


def _legacy_payload(plan, sid, col, grades_by_date):
    """Plandatei im alten Format: Noten stecken in den Tageseinträgen."""
    payload = serialize_plan(plan)
    payload["documentation"].pop("grades")
    payload["documentation"].pop("grade_conflicts")
    payload["documentation"]["sessions"] = [
        {"date": date, "entries": {str(sid): {"symbols": {}, "grades": {col: value}, "note": "", "participation": None}}}
        for date, value in grades_by_date.items()
    ]
    return payload


class TestOneGradePerColumn:
    def test_second_entry_replaces_the_first(self, graded):
        plan, sid, col = graded
        plan = record_grade(record_grade(plan, sid, col, 2.0), sid, col, 4.0)
        assert plan.documentation.grade_of(sid, col) == 4.0
        assert count_grades(plan) == 1

    def test_none_removes_the_grade(self, graded):
        plan, sid, col = graded
        plan = record_grade(record_grade(plan, sid, col, 2.0), sid, col, None)
        assert plan.documentation.grade_of(sid, col) is None
        assert plan.documentation.grades == {}

    def test_recording_creates_no_date_column(self, graded):
        plan, sid, col = graded
        assert record_grade(plan, sid, col, 2.0).documentation.sessions == []

    def test_date_operations_do_not_touch_grades(self, graded):
        plan, sid, col = graded
        plan = record_grade(plan, sid, col, 2.0)
        plan.documentation.sessions.append(Session(date="2025-09-01", entries={sid: SessionEntry(note="x")}))
        plan = rename_session_date(plan, "2025-09-01", "2025-09-02")
        assert plan.documentation.grade_of(sid, col) == 2.0

    def test_deleting_the_student_removes_grades_and_conflicts(self, graded):
        plan, sid, col = graded
        plan = record_grade(plan, sid, col, 2.0)
        plan.documentation.grade_conflicts.append(GradeConflict(sid, col, (("2025-09-01", 1.0), ("2025-09-02", 2.0))))
        result = delete_student(plan, sid)
        assert result.documentation.grades == {} and result.documentation.grade_conflicts == []


class TestLegacyFormat:
    def test_single_grade_is_taken_over_without_conflict(self, graded):
        plan, sid, col = graded
        restored = deserialize_plan(_legacy_payload(plan, sid, col, {"2025-09-01": 2.3}))
        assert restored.documentation.grade_of(sid, col) == 2.3
        assert restored.documentation.grade_conflicts == []

    def test_several_grades_keep_all_values_and_show_the_newest(self, graded):
        plan, sid, col = graded
        restored = deserialize_plan(_legacy_payload(plan, sid, col, {"2025-09-08": 4.0, "2025-09-01": 2.0}))
        assert restored.documentation.grade_of(sid, col) == 4.0
        assert restored.documentation.grade_conflicts == [
            GradeConflict(sid, col, (("2025-09-01", 2.0), ("2025-09-08", 4.0)))
        ]

    def test_equal_values_are_reported_too(self, graded):
        plan, sid, col = graded
        restored = deserialize_plan(_legacy_payload(plan, sid, col, {"2025-09-01": 2.0, "2025-09-08": 2.0}))
        assert len(restored.documentation.grade_conflicts) == 1

    def test_unknown_column_or_student_is_dropped(self, graded):
        plan, sid, col = graded
        assert deserialize_plan(_legacy_payload(plan, sid, "weg", {"2025-09-01": 2.0})).documentation.grades == {}
        stranger = StudentId.new()
        assert deserialize_plan(_legacy_payload(plan, stranger, col, {"2025-09-01": 2.0})).documentation.grades == {}

    def test_saved_format_roundtrips_and_is_no_longer_legacy(self, graded):
        plan, sid, col = graded
        restored = deserialize_plan(_legacy_payload(plan, sid, col, {"2025-09-01": 2.0, "2025-09-08": 4.0}))
        payload = serialize_plan(restored)
        assert not has_legacy_session_grades(payload)
        again = deserialize_plan(json.loads(json.dumps(payload)))
        assert again.documentation.grades == restored.documentation.grades
        assert again.documentation.grade_conflicts == restored.documentation.grade_conflicts


class TestConflicts:
    @pytest.fixture
    def conflicted(self, graded):
        plan, sid, col = graded
        return deserialize_plan(_legacy_payload(plan, sid, col, {"2025-09-01": 2.0, "2025-09-08": 4.0})), sid, col

    def test_resolving_sets_the_choice_and_ends_the_conflict(self, conflicted):
        plan, sid, col = conflicted
        result = resolve_grade_conflicts(plan, [(sid, col, 2.0)])
        assert result.documentation.grade_of(sid, col) == 2.0
        assert result.documentation.grade_conflicts == []
        assert len(plan.documentation.grade_conflicts) == 1  # Original unverändert

    def test_new_entry_decides_the_conflict(self, conflicted):
        plan, sid, col = conflicted
        assert record_grade(plan, sid, col, 1.0).documentation.grade_conflicts == []

    def test_scale_switch_converts_open_conflicts(self, conflicted):
        plan, _, _ = conflicted
        result = set_grade_scale(plan, SCALE_POINTS_0_15)
        assert result.documentation.grade_conflicts[0].candidates == (("2025-09-01", 11.0), ("2025-09-08", 5.0))


class TestLegacyBackup:
    @pytest.fixture
    def repo(self, tmp_path):
        repository = JsonSeatingPlanRepositoryV4()
        repository._backup_root_dir = lambda: tmp_path / "backups"
        return repository

    def _write_legacy(self, graded, path):
        plan, sid, col = graded
        payload = _legacy_payload(plan, sid, col, {"2025-09-01": 2.0, "2025-09-08": 4.0})
        path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _kept(self, tmp_path, path):
        return tmp_path / "backups" / path.stem / LEGACY_GRADES_BACKUP_LABEL / path.name

    def test_first_save_keeps_the_original_and_later_saves_do_not_touch_it(self, repo, graded, tmp_path):
        path = tmp_path / "plan.json"
        original = self._write_legacy(graded, path)
        loaded = repo.load_plan(path)
        repo.save_plan(loaded, path)
        assert json.loads(self._kept(tmp_path, path).read_text(encoding="utf-8")) == original
        assert not has_legacy_session_grades(json.loads(path.read_text(encoding="utf-8")))
        repo.save_plan(loaded, path)
        assert json.loads(self._kept(tmp_path, path).read_text(encoding="utf-8")) == original

    def test_rename_keeps_the_original(self, repo, graded, tmp_path):
        path = tmp_path / "plan.json"
        original = self._write_legacy(graded, path)
        repo.rename_plan(path, "Neuer Name")
        assert json.loads(self._kept(tmp_path, path).read_text(encoding="utf-8")) == original

    def test_failed_backup_aborts_the_save(self, repo, graded, tmp_path, monkeypatch):
        path = tmp_path / "plan.json"
        original = self._write_legacy(graded, path)
        loaded = repo.load_plan(path)

        def fail(*_args, **_kwargs):
            raise OSError("voll")

        monkeypatch.setattr(repo._backup, "keep_original", fail)
        with pytest.raises(OSError):
            repo.save_plan(loaded, path)
        assert json.loads(path.read_text(encoding="utf-8")) == original
