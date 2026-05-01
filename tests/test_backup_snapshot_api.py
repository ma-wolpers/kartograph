from __future__ import annotations

from app.core.domain.models import Desk, SeatingPlan
from app.infrastructure.repositories.json_plan_repository import JsonSeatingPlanRepository


def test_backup_snapshot_writes_without_primary_save(tmp_path, monkeypatch) -> None:
    repo = JsonSeatingPlanRepository()
    monkeypatch.setattr(repo, "_backup_root_dir", lambda: tmp_path / "appdata" / "Kartograph" / "backups")

    plan = SeatingPlan(
        version=3,
        plan_id="snapshot",
        name="Snapshot",
        desks=[Desk(x=0, y=0, desk_type="teacher")],
    )
    plan_path = tmp_path / "plans" / "klasse-7a.json"

    repo.backup_plan_snapshot(plan, plan_path)

    backup_dir = tmp_path / "appdata" / "Kartograph" / "backups" / "klasse-7a"
    backups = list(backup_dir.glob("*.json"))
    assert len(backups) == 1
    assert not plan_path.exists()
