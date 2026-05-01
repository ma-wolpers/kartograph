from __future__ import annotations

import json

from app.core.domain.models import Desk, DocumentationEntry, GradeColumnDefinition, SeatingPlan
from app.infrastructure.repositories.json_plan_repository import JsonSeatingPlanRepository


def _plan_with_documentation() -> SeatingPlan:
    student = Desk(x=1, y=1, desk_type="student", student_name="Alice")
    student.documentation_entries["2026-05-01"] = DocumentationEntry(
        symbols={"Beteiligung": 2},
        grades={"ka1": 2.0},
        note="arbeitete fokussiert",
    )
    student.documentation_entries["2026-05-02"] = DocumentationEntry()

    return SeatingPlan(
        version=3,
        plan_id="plan-1",
        name="Klasse 7A",
        desks=[Desk(x=0, y=0, desk_type="teacher"), student],
        documentation_dates=["2026-05-01", "2026-05-02"],
        grade_columns=[
            GradeColumnDefinition(column_id="ka1", category="schriftlich", title="KA 1"),
        ],
        written_weight_percent=40,
        sonstige_weight_percent=60,
    )


def test_repository_serializes_v3_documentation_and_prunes_empty_days(tmp_path) -> None:
    repo = JsonSeatingPlanRepository()
    plan_path = tmp_path / "klasse-7a.json"
    plan = _plan_with_documentation()

    repo.save_plan(plan, plan_path)

    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    assert payload["version"] == 3
    assert payload["documentation"]["dates"] == ["2026-05-01"]

    loaded = repo.load_plan(plan_path)
    student = loaded.desk_at(1, 1)
    assert student is not None
    assert "2026-05-01" in student.documentation_entries
    assert "2026-05-02" not in student.documentation_entries
    assert loaded.grade_columns[0].column_id == "ka1"
    assert loaded.written_weight_percent == 40
    assert loaded.sonstige_weight_percent == 60


def test_repository_migrates_v2_payload_without_documentation(tmp_path) -> None:
    repo = JsonSeatingPlanRepository()
    plan_path = tmp_path / "legacy.json"
    legacy_payload = {
        "version": 2,
        "plan_id": "legacy",
        "name": "Legacy",
        "desks": [
            {"x": 0, "y": 0, "type": "teacher", "name": "", "symbols": {}, "color_markers": []},
            {
                "x": 1,
                "y": 0,
                "type": "student",
                "name": "Alex",
                "symbols": {"Beteiligung": 2},
                "color_markers": ["gelb"],
            },
        ],
    }
    plan_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    loaded = repo.load_plan(plan_path)

    assert loaded.version == 3
    assert loaded.documentation_dates == []
    assert loaded.grade_columns == []
    assert loaded.written_weight_percent == 50
    assert loaded.sonstige_weight_percent == 50
