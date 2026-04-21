from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.core.domain.models import Desk, SeatingPlan


class JsonSeatingPlanRepository:
    def list_plans(self, plans_dir: Path) -> list[tuple[Path, SeatingPlan]]:
        plans_dir.mkdir(parents=True, exist_ok=True)
        plans: list[tuple[Path, SeatingPlan]] = []
        for path in sorted(plans_dir.glob("*.json")):
            try:
                plans.append((path, self.load_plan(path)))
            except Exception:
                continue
        return plans

    def load_plan(self, plan_path: Path) -> SeatingPlan:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
        return self._deserialize(payload)

    def save_plan(self, plan: SeatingPlan, plan_path: Path) -> None:
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._serialize(plan)
        tmp_path = plan_path.with_suffix(plan_path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(plan_path)

    def create_new_plan(self, plans_dir: Path, plan_name: str, overwrite: bool = False) -> tuple[Path, SeatingPlan]:
        plans_dir.mkdir(parents=True, exist_ok=True)
        base_name = self._slugify(plan_name or "Neuer Sitzplan")
        file_name = f"{base_name}.json"
        plan = SeatingPlan(
            version=1,
            plan_id=uuid.uuid4().hex,
            name=plan_name.strip() or "Neuer Sitzplan",
            desks=[Desk(x=0, y=0, desk_type="teacher")],
        )
        plan_path = plans_dir / file_name
        if plan_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {plan_path.name}")
        self.save_plan(plan, plan_path)
        return plan_path, plan

    def _serialize(self, plan: SeatingPlan) -> dict:
        return {
            "version": plan.version,
            "plan_id": plan.plan_id,
            "name": plan.name,
            "desks": [
                {
                    "x": desk.x,
                    "y": desk.y,
                    "type": desk.desk_type,
                    "name": desk.student_name,
                    "symbols": dict(desk.symbols),
                }
                for desk in plan.desks
            ],
        }

    def _deserialize(self, payload: dict) -> SeatingPlan:
        version = int(payload.get("version", 1))
        plan_id = str(payload.get("plan_id") or uuid.uuid4().hex)
        name = str(payload.get("name") or "Unbenannter Sitzplan")
        raw_desks = payload.get("desks")
        if not isinstance(raw_desks, list):
            raise ValueError("desks must be a list")

        desks: list[Desk] = []
        for item in raw_desks:
            if not isinstance(item, dict):
                raise ValueError("desk entry must be an object")
            x = int(item.get("x"))
            y = int(item.get("y"))
            desk_type = str(item.get("type"))
            if desk_type not in {"teacher", "student"}:
                raise ValueError("desk type must be teacher or student")
            symbols_raw = item.get("symbols") or {}
            symbols: dict[str, int] = {}

            if isinstance(symbols_raw, list):
                # Legacy format migration: ["Laptop", "Tablet"] -> {"Laptop": 1, "Tablet": 1}
                for raw_symbol in symbols_raw:
                    symbol_name = str(raw_symbol).strip()
                    if symbol_name:
                        symbols[symbol_name] = 1
            elif isinstance(symbols_raw, dict):
                for raw_symbol, raw_count in symbols_raw.items():
                    symbol_name = str(raw_symbol).strip()
                    if not symbol_name:
                        continue
                    try:
                        parsed = int(raw_count)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= parsed <= 3:
                        symbols[symbol_name] = parsed
            else:
                raise ValueError("symbols must be a list or object")

            desks.append(
                Desk(
                    x=x,
                    y=y,
                    desk_type=desk_type,
                    student_name=str(item.get("name") or "").strip(),
                    symbols=symbols,
                )
            )

        teacher_count = sum(1 for desk in desks if desk.desk_type == "teacher")
        if teacher_count != 1:
            raise ValueError("plan must contain exactly one teacher desk")
        if not any(desk.x == 0 and desk.y == 0 and desk.desk_type == "teacher" for desk in desks):
            raise ValueError("teacher desk must be at (0, 0)")

        return SeatingPlan(version=version, plan_id=plan_id, name=name, desks=desks)

    def _slugify(self, text: str) -> str:
        clean = "".join(char.lower() if char.isalnum() else "-" for char in text.strip())
        clean = "-".join(chunk for chunk in clean.split("-") if chunk)
        return clean or "sitzplan"
