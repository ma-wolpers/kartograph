"""Kartograph JSON v3 → v4 Migrationsskript.

Aufruf:
    # Einzelne Datei
    python -m app.tools.migrate_v3_to_v4 --input plans/klasse5a.json

    # Ganzes Verzeichnis (Vorschau)
    python -m app.tools.migrate_v3_to_v4 --dir plans/ --dry-run

    # Ganzes Verzeichnis mit Backup
    python -m app.tools.migrate_v3_to_v4 --dir plans/ --backup-suffix .v3.bak
"""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path


COLOR_PALETTE_DEFAULTS: dict[str, dict[str, str]] = {
    "gelb":    {"label": "Gelb",    "hex": "#f4d35e"},
    "orange":  {"label": "Orange",  "hex": "#ee964b"},
    "rot":     {"label": "Rot",     "hex": "#f95738"},
    "magenta": {"label": "Magenta", "hex": "#d81159"},
    "lila":    {"label": "Lila",    "hex": "#7b2cbf"},
    "marine":  {"label": "Marine",  "hex": "#1d3557"},
    "cyan":    {"label": "Cyan",    "hex": "#4cc9f0"},
    "tuerkis": {"label": "Türkis",  "hex": "#2a9d8f"},
    "gruen":   {"label": "Grün",    "hex": "#6a994e"},
}


def migrate_plan(v3: dict) -> dict:
    """Konvertiert einen v3-Plan-Dict in das v4-Format.

    Args:
        v3: Geparstes JSON-Dict eines Plans im v3-Format.
    """
    if v3.get("format_version") == 4:
        return v3

    color_meanings: dict[str, str] = v3.get("color_meanings") or {}
    desks: list[dict] = v3.get("desks") or []
    teacher = next((d for d in desks if d.get("type") == "teacher"), None)
    students_raw = [d for d in desks if d.get("type") == "student"]

    # Stabile student_id pro Tisch generieren
    student_id_map: dict[tuple[int, int], str] = {}
    students_v4 = []
    for desk in students_raw:
        sid = str(uuid.uuid4())
        student_id_map[(desk["x"], desk["y"])] = sid
        students_v4.append({
            "student_id": sid,
            "first_name":  desk.get("name") or "",
            "last_name":   desk.get("last_name") or "",
            "seat":        {"x": desk["x"], "y": desk["y"]},
            "diagnostic":  {
                "symbols":    desk.get("symbols") or {},
                "color_tags": desk.get("color_markers") or [],
            },
        })

    # Tischgruppen aus Desk-Geometrie aufbauen
    groups: dict[int, list[dict]] = {}
    for desk in students_raw:
        group_num = int(desk.get("tablegroup_number") or 0)
        if group_num == 0:
            continue
        groups.setdefault(group_num, []).append({
            "x":        desk["x"],
            "y":        desk["y"],
            "shift_x":  float(desk.get("tablegroup_shift_x") or 0.0),
            "shift_y":  float(desk.get("tablegroup_shift_y") or 0.0),
            "rotation": float(desk.get("tablegroup_rotation") or 0.0),
        })
    tablegroups_v4 = [
        {"group_id": gid, "seats": seats}
        for gid, seats in sorted(groups.items())
    ]

    # Farb-Palette: nur tatsächlich verwendete Farben einschließen
    color_palette: dict[str, dict] = {}
    for key, defaults in COLOR_PALETTE_DEFAULTS.items():
        if not any(key in (d.get("color_markers") or []) for d in students_raw):
            continue
        color_palette[key] = {
            **defaults,
            "meaning": color_meanings.get(key, ""),
        }

    # Sessions aus documentation_entries aller Desks aufbauen
    docs_raw: dict = v3.get("documentation") or {}
    sessions_by_date: dict[str, dict] = {}
    for desk in students_raw:
        sid = student_id_map[(desk["x"], desk["y"])]
        for date, entry in (desk.get("documentation_entries") or {}).items():
            if not isinstance(entry, dict):
                continue
            sessions_by_date.setdefault(date, {})[sid] = {
                "symbols": entry.get("symbols") or {},
                "grades":  entry.get("grades") or {},
                "note":    entry.get("note") or "",
            }
    sessions_v4 = [
        {"date": date, "entries": entries}
        for date, entries in sorted(sessions_by_date.items())
    ]

    # grade_columns: "id" → "column_id"
    grade_columns_v4 = []
    for col in (docs_raw.get("grade_columns") or []):
        if not isinstance(col, dict):
            continue
        col_id = col.get("id") or col.get("column_id") or ""
        if not col_id:
            continue
        grade_columns_v4.append({
            "column_id":  col_id,
            "category":   col.get("category") or "sonstig",
            "title":      col.get("title") or "",
            "created_at": "",
        })

    weighting = docs_raw.get("grade_weighting") or {}

    now = datetime.now().isoformat(timespec="seconds")
    return {
        "format_version": 4,
        "plan_id":        v3.get("plan_id") or str(uuid.uuid4()),
        "meta": {
            "name":          v3.get("name") or "",
            "school_year":   "",
            "created_at":    now,
            "last_modified": now,
        },
        "classroom": {
            "teacher_seat": (
                {"x": teacher["x"], "y": teacher["y"]} if teacher else {"x": 0, "y": 0}
            ),
            "students": students_v4,
        },
        "tablegroups":   tablegroups_v4,
        "color_palette": color_palette,
        "documentation": {
            "grade_columns":   grade_columns_v4,
            "grade_weighting": {
                "written_percent":  int(weighting.get("written_percent") or 50),
                "sonstige_percent": int(weighting.get("sonstige_percent") or 50),
            },
            "sessions": sessions_v4,
        },
    }


def migrate_file(
    input_path: Path,
    output_path: Path | None = None,
    backup_suffix: str | None = ".v3.bak",
    dry_run: bool = False,
) -> None:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if raw.get("format_version") == 4:
        print(f"  SKIP (already v4): {input_path.name}")
        return

    v4 = migrate_plan(raw)
    target = output_path or input_path

    if dry_run:
        student_count = len(v4["classroom"]["students"])
        session_count = len(v4["documentation"]["sessions"])
        print(
            f"  DRY-RUN: {input_path.name} → {target.name}"
            f"  ({student_count} Schüler, {session_count} Sessions)"
        )
        return

    if backup_suffix and input_path == target:
        backup_path = input_path.parent / (input_path.name + backup_suffix)
        shutil.copy2(input_path, backup_path)

    target.write_text(json.dumps(v4, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  OK: {input_path.name} → {target.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kartograph JSON v3 → v4 Migration")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path, help="Einzelne .json-Datei")
    group.add_argument("--dir",   type=Path, help="Verzeichnis mit .json-Dateien")
    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--backup-suffix", default=".v3.bak",
                        help="Suffix das an Backup-Dateien angehängt wird (default: .v3.bak)")
    parser.add_argument("--output", type=Path,
                        help="Ausgabepfad (nur bei --input; überschreibt --backup-suffix)")
    args = parser.parse_args()

    files: list[Path] = [args.input] if args.input else sorted(args.dir.glob("*.json"))
    if not files:
        print("Keine JSON-Dateien gefunden.")
        return

    backup = None if args.output else args.backup_suffix
    for f in files:
        try:
            migrate_file(f, args.output if args.input else None, backup, args.dry_run)
        except Exception as exc:
            print(f"  ERROR: {f.name}: {exc}")


if __name__ == "__main__":
    main()
