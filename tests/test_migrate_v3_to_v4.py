"""Tests für das Migrationsskript v3 → v4."""

import json
import shutil
from pathlib import Path

import pytest

from app.tools.migrate_v3_to_v4 import migrate_file, migrate_plan
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def v3_plan():
    """Minimaler, vollständiger v3-Plan."""
    return {
        "version": 3,
        "plan_id": "abc123",
        "name": "Klasse 5a",
        "color_meanings": {"gelb": "Förderbedarf", "rot": "Hochbegabt"},
        "desks": [
            {"type": "teacher", "x": 0, "y": 0},
            {
                "type": "student", "x": 1, "y": 0,
                "name": "Anna", "last_name": "Müller",
                "symbols": {"Laptop": 2},
                "color_markers": ["gelb"],
                "tablegroup_number": 1,
                "tablegroup_shift_x": 0.03,
                "tablegroup_shift_y": -0.02,
                "tablegroup_rotation": 1.5,
                "documentation_entries": {
                    "2025-09-01": {
                        "symbols": {"Beteiligung": 3},
                        "grades": {"col001": 2.5},
                        "note": "Sehr konzentriert",
                    }
                },
            },
            {
                "type": "student", "x": 2, "y": 0,
                "name": "Ben", "last_name": "Koch",
                "symbols": {},
                "color_markers": [],
                "tablegroup_number": 1,
                "tablegroup_shift_x": -0.03,
                "tablegroup_shift_y": 0.02,
                "tablegroup_rotation": -1.5,
                "documentation_entries": {},
            },
        ],
        "documentation": {
            "grade_columns": [
                {"id": "col001", "category": "schriftlich", "title": "Mathearbeit 1"}
            ],
            "grade_weighting": {"written_percent": 60, "sonstige_percent": 40},
        },
    }


# ---------------------------------------------------------------------------
# migrate_plan — Format & Struktur
# ---------------------------------------------------------------------------

class TestMigratePlanFormat:
    def test_format_version_is_4(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert v4["format_version"] == 4

    def test_plan_id_preserved(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert v4["plan_id"] == "abc123"

    def test_meta_name_preserved(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert v4["meta"]["name"] == "Klasse 5a"

    def test_meta_has_timestamps(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert v4["meta"]["created_at"]
        assert v4["meta"]["last_modified"]

    def test_teacher_seat_extracted(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        ts = v4["classroom"]["teacher_seat"]
        assert ts == {"x": 0, "y": 0}

    def test_teacher_not_in_students(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        for s in v4["classroom"]["students"]:
            assert s["seat"] != {"x": 0, "y": 0}


class TestMigratePlanStudents:
    def test_student_count(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert len(v4["classroom"]["students"]) == 2

    def test_student_names_preserved(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        anna = next(s for s in v4["classroom"]["students"] if s["first_name"] == "Anna")
        assert anna["last_name"] == "Müller"

    def test_seat_coordinates(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        anna = next(s for s in v4["classroom"]["students"] if s["first_name"] == "Anna")
        assert anna["seat"] == {"x": 1, "y": 0}

    def test_diagnostic_symbols(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        anna = next(s for s in v4["classroom"]["students"] if s["first_name"] == "Anna")
        assert anna["diagnostic"]["symbols"] == {"Laptop": 2}

    def test_diagnostic_color_tags(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        anna = next(s for s in v4["classroom"]["students"] if s["first_name"] == "Anna")
        assert anna["diagnostic"]["color_tags"] == ["gelb"]

    def test_each_student_gets_unique_id(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        ids = {s["student_id"] for s in v4["classroom"]["students"]}
        assert len(ids) == 2


class TestMigratePlanTablegroups:
    def test_tablegroup_built(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert len(v4["tablegroups"]) == 1
        assert v4["tablegroups"][0]["group_id"] == 1

    def test_tablegroup_has_two_seats(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert len(v4["tablegroups"][0]["seats"]) == 2

    def test_geometry_preserved(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        anna_seat = next(
            s for s in v4["tablegroups"][0]["seats"] if s["x"] == 1
        )
        assert anna_seat["shift_x"] == pytest.approx(0.03)
        assert anna_seat["rotation"] == pytest.approx(1.5)

    def test_no_tablegroup_for_ungrouped_students(self):
        v3 = {
            "version": 3,
            "plan_id": "x",
            "name": "T",
            "desks": [
                {"type": "teacher", "x": 0, "y": 0},
                {"type": "student", "x": 1, "y": 0, "name": "A", "last_name": "",
                 "symbols": {}, "color_markers": [], "tablegroup_number": 0,
                 "documentation_entries": {}},
            ],
            "documentation": {},
        }
        v4 = migrate_plan(v3)
        assert v4["tablegroups"] == []


class TestMigratePlanColorPalette:
    def test_used_colors_included(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert "gelb" in v4["color_palette"]

    def test_unused_colors_excluded(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert "rot" not in v4["color_palette"]  # rot nicht verwendet

    def test_meaning_merged(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert v4["color_palette"]["gelb"]["meaning"] == "Förderbedarf"

    def test_hex_value_present(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        assert v4["color_palette"]["gelb"]["hex"].startswith("#")


class TestMigratePlanSessions:
    def test_session_created_for_date(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        sessions = v4["documentation"]["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["date"] == "2025-09-01"

    def test_session_entry_mapped_by_student_id(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        session = v4["documentation"]["sessions"][0]
        anna = next(s for s in v4["classroom"]["students"] if s["first_name"] == "Anna")
        entry = session["entries"][anna["student_id"]]
        assert entry["symbols"] == {"Beteiligung": 3}
        assert entry["grades"] == {"col001": 2.5}
        assert entry["note"] == "Sehr konzentriert"

    def test_grade_column_id_renamed(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        cols = v4["documentation"]["grade_columns"]
        assert cols[0]["column_id"] == "col001"
        assert "id" not in cols[0]

    def test_grade_weighting_preserved(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        w = v4["documentation"]["grade_weighting"]
        assert w["written_percent"] == 60
        assert w["sonstige_percent"] == 40


# ---------------------------------------------------------------------------
# Idempotenz
# ---------------------------------------------------------------------------

class TestIdempotenz:
    def test_already_v4_returned_unchanged(self, v3_plan):
        v4 = migrate_plan(v3_plan)
        v4_again = migrate_plan(v4)
        assert v4_again is v4

    def test_migrate_file_skips_v4(self, tmp_path, v3_plan):
        v4_data = migrate_plan(v3_plan)
        f = tmp_path / "plan.json"
        f.write_text(json.dumps(v4_data), encoding="utf-8")
        mtime_before = f.stat().st_mtime
        migrate_file(f, backup_suffix=None)
        assert f.stat().st_mtime == mtime_before  # Datei unverändert


# ---------------------------------------------------------------------------
# migrate_file — Dateisystem
# ---------------------------------------------------------------------------

class TestMigrateFile:
    def test_writes_v4_file(self, tmp_path, v3_plan):
        f = tmp_path / "plan.json"
        f.write_text(json.dumps(v3_plan), encoding="utf-8")
        migrate_file(f, backup_suffix=None)
        result = json.loads(f.read_text(encoding="utf-8"))
        assert result["format_version"] == 4

    def test_creates_backup(self, tmp_path, v3_plan):
        f = tmp_path / "plan.json"
        f.write_text(json.dumps(v3_plan), encoding="utf-8")
        migrate_file(f, backup_suffix=".v3.bak")
        backup = tmp_path / "plan.json.v3.bak"
        assert backup.exists()
        original = json.loads(backup.read_text(encoding="utf-8"))
        assert original.get("version") == 3

    def test_dry_run_does_not_modify(self, tmp_path, v3_plan):
        f = tmp_path / "plan.json"
        f.write_text(json.dumps(v3_plan), encoding="utf-8")
        migrate_file(f, backup_suffix=None, dry_run=True)
        result = json.loads(f.read_text(encoding="utf-8"))
        assert result.get("version") == 3  # unverändert

    def test_output_path(self, tmp_path, v3_plan):
        src = tmp_path / "src.json"
        dst = tmp_path / "dst.json"
        src.write_text(json.dumps(v3_plan), encoding="utf-8")
        migrate_file(src, output_path=dst, backup_suffix=None)
        result = json.loads(dst.read_text(encoding="utf-8"))
        assert result["format_version"] == 4
        original = json.loads(src.read_text(encoding="utf-8"))
        assert original.get("version") == 3  # Quelle unberührt


# ---------------------------------------------------------------------------
# Roundtrip: v3 migrieren → v4-Deserializer lesen
# ---------------------------------------------------------------------------

class TestMigrateAndDeserialize:
    def test_migrated_plan_deserializes_cleanly(self, v3_plan):
        v4_dict = migrate_plan(v3_plan)
        plan = deserialize_plan(v4_dict)
        assert len(plan.classroom.students) == 2
        assert plan.documentation.grade_columns[0].column_id == "col001"
        assert len(plan.documentation.sessions) == 1

    def test_student_ids_are_valid_student_ids(self, v3_plan):
        from app.core.domain.student_id import StudentId
        v4_dict = migrate_plan(v3_plan)
        plan = deserialize_plan(v4_dict)
        for s in plan.classroom.students:
            assert isinstance(s.student_id, StudentId)
            assert len(s.student_id) == 32
