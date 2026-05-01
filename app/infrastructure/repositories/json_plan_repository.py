from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

from app.core.domain.models import DocumentationEntry, GradeColumnDefinition, SeatingPlan, Desk
from app.core.domain.table_groups import normalize_tablegroups_in_place


class JsonSeatingPlanRepository:
    def _coerce_int(self, raw_value: object, default: int) -> int:
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return default

    def _coerce_float(self, raw_value: object, default: float) -> float:
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return default

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
            version=3,
            plan_id=uuid.uuid4().hex,
            name=plan_name.strip() or "Neuer Sitzplan",
            desks=[Desk(x=0, y=0, desk_type="teacher")],
        )
        plan_path = plans_dir / file_name
        if plan_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {plan_path.name}")
        self.save_plan(plan, plan_path)
        return plan_path, plan

    def rename_plan(self, source_path: Path, new_name: str, overwrite: bool = False) -> tuple[Path, SeatingPlan]:
        source_plan = self.load_plan(source_path)
        target_name = new_name.strip() or source_plan.name
        target_path = source_path.with_name(f"{self._slugify(target_name)}.json")

        source_plan.name = target_name

        if target_path != source_path and target_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {target_path.name}")

        if target_path == source_path:
            self.save_plan(source_plan, source_path)
            return source_path, source_plan

        self.save_plan(source_plan, target_path)
        source_path.unlink(missing_ok=True)
        return target_path, source_plan

    def delete_plan(self, plan_path: Path) -> None:
        if not plan_path.exists():
            raise FileNotFoundError(f"Plandatei nicht gefunden: {plan_path.name}")
        plan_path.unlink()

    def duplicate_plan(self, source_path: Path, target_name: str, overwrite: bool = False) -> tuple[Path, SeatingPlan]:
        source_plan = self.load_plan(source_path)
        duplicated = SeatingPlan(
            version=source_plan.version,
            plan_id=uuid.uuid4().hex,
            name=target_name.strip() or source_plan.name,
            desks=deepcopy(source_plan.desks),
            color_meanings=dict(source_plan.color_meanings),
            documentation_dates=list(source_plan.documentation_dates),
            grade_columns=deepcopy(source_plan.grade_columns),
            written_weight_percent=int(source_plan.written_weight_percent),
            sonstige_weight_percent=int(source_plan.sonstige_weight_percent),
        )
        target_path = source_path.with_name(f"{self._slugify(duplicated.name)}.json")
        if target_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {target_path.name}")
        self.save_plan(duplicated, target_path)
        return target_path, duplicated

    def _serialize(self, plan: SeatingPlan) -> dict:
        dates_in_use: set[str] = set()
        serialized_desks = []

        for desk in plan.desks:
            raw_entries = desk.documentation_entries or {}
            serialized_entries: dict[str, dict] = {}
            for raw_date, raw_entry in raw_entries.items():
                date_key = str(raw_date).strip()
                if not date_key:
                    continue
                entry = raw_entry
                if not isinstance(entry, DocumentationEntry):
                    continue
                symbols: dict[str, int] = {}
                for raw_symbol, raw_value in entry.symbols.items():
                    symbol = str(raw_symbol).strip()
                    if not symbol:
                        continue
                    try:
                        parsed_value = int(raw_value)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= parsed_value <= 3:
                        symbols[symbol] = parsed_value

                grades: dict[str, float] = {}
                for raw_column_id, raw_grade in entry.grades.items():
                    column_id = str(raw_column_id).strip()
                    if not column_id:
                        continue
                    try:
                        parsed_grade = float(raw_grade)
                    except (TypeError, ValueError):
                        continue
                    grades[column_id] = parsed_grade
                note = entry.note.strip()
                if not symbols and not grades and not note:
                    continue
                serialized_entries[date_key] = {
                    "symbols": symbols,
                    "grades": grades,
                    "note": note,
                }
                dates_in_use.add(date_key)

            serialized_desks.append(
                {
                    "x": desk.x,
                    "y": desk.y,
                    "type": desk.desk_type,
                    "name": desk.student_name,
                    "symbols": dict(desk.symbols),
                    "color_markers": list(desk.color_markers),
                    "tablegroup_number": int(desk.tablegroup_number),
                    "tablegroup_shift_x": float(desk.tablegroup_shift_x),
                    "tablegroup_shift_y": float(desk.tablegroup_shift_y),
                    "tablegroup_rotation": float(desk.tablegroup_rotation),
                    "documentation_entries": serialized_entries,
                }
            )

        effective_dates = sorted(dates_in_use)

        serialized_grade_columns = []
        seen_column_ids: set[str] = set()
        for column in plan.grade_columns:
            column_id = str(column.column_id).strip()
            title = str(column.title).strip()
            category = str(column.category).strip().lower()
            if not column_id or column_id in seen_column_ids:
                continue
            if category not in {"schriftlich", "sonstig"}:
                continue
            serialized_grade_columns.append(
                {
                    "id": column_id,
                    "category": category,
                    "title": title or column_id,
                }
            )
            seen_column_ids.add(column_id)

        written_weight = self._coerce_int(plan.written_weight_percent, 50)
        sonstige_weight = self._coerce_int(plan.sonstige_weight_percent, 50)
        total = written_weight + sonstige_weight
        if total <= 0:
            written_weight, sonstige_weight = 50, 50

        return {
            "version": max(int(plan.version), 3),
            "plan_id": plan.plan_id,
            "name": plan.name,
            "color_meanings": dict(plan.color_meanings),
            "documentation": {
                "dates": effective_dates,
                "grade_columns": serialized_grade_columns,
                "grade_weighting": {
                    "written_percent": written_weight,
                    "sonstige_percent": sonstige_weight,
                },
            },
            "desks": serialized_desks,
        }

    def _deserialize(self, payload: dict) -> SeatingPlan:
        version = int(payload.get("version", 1))
        plan_id = str(payload.get("plan_id") or uuid.uuid4().hex)
        name = str(payload.get("name") or "Unbenannter Sitzplan")

        documentation_payload = payload.get("documentation") if isinstance(payload.get("documentation"), dict) else {}
        dates_raw = documentation_payload.get("dates") if isinstance(documentation_payload, dict) else []
        documentation_dates: list[str] = []
        if isinstance(dates_raw, list):
            for raw_date in dates_raw:
                date_key = str(raw_date).strip()
                if date_key and date_key not in documentation_dates:
                    documentation_dates.append(date_key)

        grade_columns_raw = documentation_payload.get("grade_columns") if isinstance(documentation_payload, dict) else []
        grade_columns: list[GradeColumnDefinition] = []
        if isinstance(grade_columns_raw, list):
            for raw_column in grade_columns_raw:
                if not isinstance(raw_column, dict):
                    continue
                column_id = str(raw_column.get("id") or "").strip()
                category = str(raw_column.get("category") or "").strip().lower()
                title = str(raw_column.get("title") or "").strip()
                if not column_id or category not in {"schriftlich", "sonstig"}:
                    continue
                if any(existing.column_id == column_id for existing in grade_columns):
                    continue
                grade_columns.append(
                    GradeColumnDefinition(
                        column_id=column_id,
                        category=category,
                        title=title or column_id,
                    )
                )

        grade_weighting = documentation_payload.get("grade_weighting") if isinstance(documentation_payload, dict) else {}
        if not isinstance(grade_weighting, dict):
            grade_weighting = {}
        written_weight = self._coerce_int(grade_weighting.get("written_percent", 50), 50)
        sonstige_weight = self._coerce_int(grade_weighting.get("sonstige_percent", 50), 50)
        if written_weight + sonstige_weight <= 0:
            written_weight = 50
            sonstige_weight = 50

        color_meanings_raw = payload.get("color_meanings") or {}
        color_meanings: dict[str, str] = {}
        if isinstance(color_meanings_raw, dict):
            for raw_key, raw_meaning in color_meanings_raw.items():
                key = str(raw_key).strip()
                meaning = str(raw_meaning).strip()
                if key and meaning:
                    color_meanings[key] = meaning
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

            color_markers_raw = item.get("color_markers") or []
            color_markers: list[str] = []
            if isinstance(color_markers_raw, list):
                for raw_color in color_markers_raw:
                    color_key = str(raw_color).strip()
                    if color_key and color_key not in color_markers:
                        color_markers.append(color_key)
            elif isinstance(color_markers_raw, str):
                color_key = color_markers_raw.strip()
                if color_key:
                    color_markers.append(color_key)
            else:
                raise ValueError("color_markers must be a list or string")

            documentation_entries_raw = item.get("documentation_entries")
            documentation_entries: dict[str, DocumentationEntry] = {}
            if isinstance(documentation_entries_raw, dict):
                for raw_date, raw_entry in documentation_entries_raw.items():
                    date_key = str(raw_date).strip()
                    if not date_key or not isinstance(raw_entry, dict):
                        continue

                    symbols: dict[str, int] = {}
                    symbols_raw = raw_entry.get("symbols")
                    if isinstance(symbols_raw, dict):
                        for raw_symbol, raw_count in symbols_raw.items():
                            symbol_name = str(raw_symbol).strip()
                            if not symbol_name:
                                continue
                            try:
                                parsed_count = int(raw_count)
                            except (TypeError, ValueError):
                                continue
                            if 1 <= parsed_count <= 3:
                                symbols[symbol_name] = parsed_count

                    grades: dict[str, float] = {}
                    grades_raw = raw_entry.get("grades")
                    if isinstance(grades_raw, dict):
                        for raw_column_id, raw_grade in grades_raw.items():
                            column_id = str(raw_column_id).strip()
                            if not column_id:
                                continue
                            try:
                                parsed_grade = float(raw_grade)
                            except (TypeError, ValueError):
                                continue
                            grades[column_id] = parsed_grade

                    note = str(raw_entry.get("note") or "").strip()
                    entry = DocumentationEntry(symbols=symbols, grades=grades, note=note)
                    if entry.has_content():
                        documentation_entries[date_key] = entry
                        if date_key not in documentation_dates:
                            documentation_dates.append(date_key)

            desks.append(
                Desk(
                    x=x,
                    y=y,
                    desk_type=desk_type,
                    student_name=str(item.get("name") or "").strip(),
                    symbols=symbols,
                    color_markers=color_markers,
                    tablegroup_number=self._coerce_int(item.get("tablegroup_number", 0), 0),
                    tablegroup_shift_x=self._coerce_float(item.get("tablegroup_shift_x", 0.0), 0.0),
                    tablegroup_shift_y=self._coerce_float(item.get("tablegroup_shift_y", 0.0), 0.0),
                    tablegroup_rotation=self._coerce_float(item.get("tablegroup_rotation", 0.0), 0.0),
                    documentation_entries=documentation_entries,
                )
            )

        teacher_count = sum(1 for desk in desks if desk.desk_type == "teacher")
        if teacher_count != 1:
            raise ValueError("plan must contain exactly one teacher desk")
        if not any(desk.x == 0 and desk.y == 0 and desk.desk_type == "teacher" for desk in desks):
            raise ValueError("teacher desk must be at (0, 0)")

        used_colors = {
            color_key
            for desk in desks
            if desk.desk_type == "student"
            for color_key in desk.color_markers
        }
        normalized_color_meanings = {key: value for key, value in color_meanings.items() if key in used_colors}

        plan = SeatingPlan(
            version=max(version, 3),
            plan_id=plan_id,
            name=name,
            desks=desks,
            color_meanings=normalized_color_meanings,
            documentation_dates=sorted(set(documentation_dates)),
            grade_columns=grade_columns,
            written_weight_percent=written_weight,
            sonstige_weight_percent=sonstige_weight,
        )
        normalize_tablegroups_in_place(plan)
        return plan

    def _slugify(self, text: str) -> str:
        clean = "".join(char.lower() if char.isalnum() else "-" for char in text.strip())
        clean = "-".join(chunk for chunk in clean.split("-") if chunk)
        return clean or "sitzplan"
