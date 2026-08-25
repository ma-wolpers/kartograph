"""Roundtrip-Test: SeatingPlan → serialize → JSON → deserialize → vergleichen."""

import json

import pytest

from app.core.domain.models_v4 import (
    CustomSymbolDefinition,
    GradeColumn,
    GradeWeighting,
    GroupSeat,
    PaletteEntry,
    Session,
    SessionEntry,
    TableGroup,
)
from app.core.domain.student_id import StudentId
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan
from tests.conftest import make_plan, make_student


def _roundtrip(plan):
    payload = serialize_plan(plan)
    json_str = json.dumps(payload, ensure_ascii=False)
    payload2 = json.loads(json_str)
    return deserialize_plan(payload2)


class TestBasicRoundtrip:
    def test_empty_plan_roundtrip(self, plan):
        restored = _roundtrip(plan)
        assert restored.format_version == 4
        assert restored.meta.name == "Testplan"
        assert restored.classroom.teacher_seat.x == 0

    def test_student_preserved(self, anna_id, plan_with_anna):
        restored = _roundtrip(plan_with_anna)
        s = restored.student_by_id(anna_id)
        assert s is not None
        assert s.first_name == "Anna"
        assert s.last_name == "Müller"
        assert s.seat.x == 1

    def test_student_id_preserved(self, anna_id, plan_with_anna):
        restored = _roundtrip(plan_with_anna)
        assert restored.student_by_id(anna_id) is not None

    def test_diagnostic_symbols_preserved(self):
        sid = StudentId.new()
        s = make_student(student_id=sid)
        s.diagnostic.symbols = {"Laptop": 2}
        plan = make_plan(students=[s])
        restored = _roundtrip(plan)
        assert restored.student_by_id(sid).diagnostic.symbols == {"Laptop": 2}

    def test_color_tags_preserved(self):
        sid = StudentId.new()
        s = make_student(student_id=sid)
        s.diagnostic.color_tags = ["gelb", "rot"]
        plan = make_plan(students=[s])
        restored = _roundtrip(plan)
        assert restored.student_by_id(sid).diagnostic.color_tags == ["gelb", "rot"]

    def test_accommodations_preserved(self):
        sid = StudentId.new()
        s = make_student(student_id=sid)
        s.diagnostic.accommodations = ["Zeitzuschlag 25 %", "Nutzung Laptop"]
        plan = make_plan(students=[s])
        restored = _roundtrip(plan)
        assert restored.student_by_id(sid).diagnostic.accommodations == ["Zeitzuschlag 25 %", "Nutzung Laptop"]

    def test_accommodations_default_empty_when_missing_in_json(self):
        """Abwärtskompatibilität: v4-Pläne von vor dieser Erweiterung haben kein 'accommodations'-Feld."""
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        payload = serialize_plan(plan)
        del payload["classroom"]["students"][0]["diagnostic"]["accommodations"]
        restored = deserialize_plan(payload)
        assert restored.student_by_id(sid).diagnostic.accommodations == []

    def test_nickname_preserved(self):
        sid = StudentId.new()
        s = make_student(student_id=sid, first_name="Alexander", nickname="Alex")
        plan = make_plan(students=[s])
        restored = _roundtrip(plan)
        restored_student = restored.student_by_id(sid)
        assert restored_student.nickname == "Alex"
        assert restored_student.first_name_official == "Alexander"
        assert restored_student.first_name == "Alex"

    def test_nickname_default_empty_when_missing_in_json(self):
        """Abwärtskompatibilität: Pläne von vor der Spitzname-Erweiterung haben kein 'nickname'-Feld."""
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid, first_name="Anna")])
        payload = serialize_plan(plan)
        del payload["classroom"]["students"][0]["nickname"]
        restored = deserialize_plan(payload)
        s = restored.student_by_id(sid)
        assert s.nickname == ""
        assert s.first_name == "Anna"


class TestTableGroupRoundtrip:
    def test_tablegroup_preserved(self, plan):
        plan.tablegroups = [
            TableGroup(group_id=1, seats=[
                GroupSeat(x=1, y=0, shift_x=0.03, shift_y=-0.02, rotation=1.5),
                GroupSeat(x=2, y=0),
            ])
        ]
        restored = _roundtrip(plan)
        assert len(restored.tablegroups) == 1
        assert restored.tablegroups[0].group_id == 1
        gs = restored.tablegroups[0].seats[0]
        assert gs.shift_x == pytest.approx(0.03)
        assert gs.rotation == pytest.approx(1.5)


class TestColorPaletteRoundtrip:
    def test_palette_preserved(self, plan):
        plan.color_palette = {
            "gelb": PaletteEntry(label="Gelb", hex="#f4d35e", meaning="Förderbedarf"),
        }
        restored = _roundtrip(plan)
        entry = restored.color_palette.get("gelb")
        assert entry is not None
        assert entry.meaning == "Förderbedarf"
        assert entry.hex == "#f4d35e"


class TestCustomSymbolsRoundtrip:
    def test_custom_symbol_preserved(self, plan):
        plan.custom_symbols = {
            "abc123": CustomSymbolDefinition(id="abc123", glyph="☕", meaning="Kaffee vergessen", shortcut="Ctrl+Shift+K"),
        }
        restored = _roundtrip(plan)
        entry = restored.custom_symbols.get("abc123")
        assert entry is not None
        assert entry.id == "abc123"
        assert entry.glyph == "☕"
        assert entry.meaning == "Kaffee vergessen"
        assert entry.shortcut == "Ctrl+Shift+K"

    def test_missing_field_defaults_to_empty(self, plan):
        """Altes Planformat ohne custom_symbols-Feld laedt weiterhin klaglos."""
        payload = serialize_plan(plan)
        del payload["custom_symbols"]
        restored = deserialize_plan(payload)
        assert restored.custom_symbols == {}

    def test_corrupted_shortcut_does_not_prevent_loading(self, plan):
        """Deserializer ist bewusst lenient: ein von Hand kaputt gemachter
        Shortcut-Wert fuehrt nicht zum Ladefehler des ganzen Plans."""
        payload = serialize_plan(plan)
        payload["custom_symbols"] = {
            "abc123": {"id": "abc123", "glyph": "☕", "meaning": "Kaffee vergessen", "shortcut": "not-a-valid-shortcut"},
        }
        restored = deserialize_plan(payload)
        entry = restored.custom_symbols.get("abc123")
        assert entry is not None
        assert entry.shortcut == "not-a-valid-shortcut"


class TestDocumentationRoundtrip:
    def test_grade_columns_preserved(self, plan):
        plan.documentation.grade_columns = [
            GradeColumn(column_id="abc12345", category="schriftlich", title="Mathe 1")
        ]
        restored = _roundtrip(plan)
        col = restored.documentation.column_by_id("abc12345")
        assert col is not None
        assert col.title == "Mathe 1"

    def test_grade_weighting_preserved(self, plan):
        plan.documentation.weighting = GradeWeighting(written_percent=60, sonstige_percent=40)
        restored = _roundtrip(plan)
        assert restored.documentation.weighting.written_percent == 60

    def test_session_with_entries_preserved(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        session = Session(
            date="2025-09-01",
            entries={sid: SessionEntry(symbols={"Beteiligung": 2}, note="Gut")},
        )
        plan.documentation.sessions.append(session)
        plan.documentation.grade_columns = [
            GradeColumn(column_id="col00001", category="schriftlich", title="A")
        ]

        restored = _roundtrip(plan)
        rs = restored.documentation.session_for_date("2025-09-01")
        assert rs is not None
        entry = rs.entries.get(sid)
        assert entry is not None
        assert entry.symbols == {"Beteiligung": 2}
        assert entry.note == "Gut"

    def test_empty_session_not_serialized(self):
        plan = make_plan()
        plan.documentation.sessions = [Session(date="2025-09-01")]
        payload = serialize_plan(plan)
        assert payload["documentation"]["sessions"] == []

    def test_participation_rating_preserved(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        session = Session(date="2025-09-01", entries={sid: SessionEntry(participation="+")})
        plan.documentation.sessions.append(session)

        restored = _roundtrip(plan)
        entry = restored.documentation.session_for_date("2025-09-01").entries.get(sid)
        assert entry is not None
        assert entry.participation == "+"

    def test_participation_rating_star_preserved(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        session = Session(date="2025-09-01", entries={sid: SessionEntry(participation="☆")})
        plan.documentation.sessions.append(session)

        restored = _roundtrip(plan)
        entry = restored.documentation.session_for_date("2025-09-01").entries.get(sid)
        assert entry is not None
        assert entry.participation == "☆"

    def test_participation_defaults_to_none_when_missing_in_json(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        session = Session(date="2025-09-01", entries={sid: SessionEntry(note="Gut")})
        plan.documentation.sessions.append(session)
        payload = serialize_plan(plan)

        # Simuliert eine alte Plandatei ohne das "participation"-Feld.
        del payload["documentation"]["sessions"][0]["entries"][str(sid)]["participation"]
        restored = deserialize_plan(payload)

        entry = restored.documentation.session_for_date("2025-09-01").entries.get(sid)
        assert entry is not None
        assert entry.participation is None
        assert entry.note == "Gut"
