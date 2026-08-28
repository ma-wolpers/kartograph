"""Perf-Benchmark + Regressionscheck für die Dokumentationstabelle (v4).

Vergleicht die alte, pro (Schüler x Notenspalte) neu sortierende Berechnung
gegen die aktuelle Implementierung (ein Durchlauf über alle Sessions für
alle Schüler gleichzeitig, siehe ``compute_latest_grades_by_student`` /
``summarize_latest_symbols_by_student`` in ``app.core.usecases.v4``).

Nutzt ausschließlich synthetische Testdaten (erfundene Namen) — niemals
echte Plandateien. Reproduzierbares Szenario statt großem Testsystem, wie
in der Performance-Analyse (2026-08-28) vereinbart.

Aufruf:
    python -m app.tools.perf_bench_docs_table
    python -m app.tools.perf_bench_docs_table --students 40 --sessions 80 --grade-columns 6
"""

from __future__ import annotations

import argparse
import datetime
import random
import time

from app.core.domain.models_v4 import (
    Classroom,
    DocumentationBlock,
    GradeColumn,
    PlanMeta,
    Seat,
    SeatingPlan,
    Session,
    SessionEntry,
    Student,
    TeacherSeat,
)
from app.core.domain.student_id import StudentId
from app.core.usecases.v4._shared import _round_half_up_to_int, _round_half_up_to_two_decimals
from app.core.usecases.v4.grade_usecases import (
    collect_grade_value_lists_by_student,
    compute_grade_display_by_student,
    compute_grade_subtotal_display_by_student,
    compute_latest_grades_by_student,
)
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols_by_student
from app.tools._perf_bench_docs_table_tk_checks import (
    check_treeview_item_update_matches_reinsert,
    count_tcl_calls_for_single_cell_edit,
)


def build_synthetic_plan(num_students: int, num_sessions: int, num_grade_columns: int) -> SeatingPlan:
    """Baut einen rein synthetischen Plan (erfundene Namen) für Benchmark-Zwecke.

    Args:
        num_students: Anzahl der (immer benannten) Test-Schüler.
        num_sessions: Anzahl der Dokumentations-Sessions.
        num_grade_columns: Anzahl der Notenspalten (abwechselnd schriftlich/sonstig).
    """
    students = [
        Student(
            student_id=StudentId.new(),
            first_name_official=f"Test{i}",
            last_name=f"Schueler{i}",
            seat=Seat(x=i % 10, y=i // 10),
        )
        for i in range(num_students)
    ]
    classroom = Classroom(teacher_seat=TeacherSeat(x=-1, y=-1), students=students)

    grade_columns = [
        GradeColumn(
            column_id=f"col{i}",
            category="schriftlich" if i % 2 == 0 else "sonstig",
            title=f"Note {i}",
        )
        for i in range(max(1, num_grade_columns))
    ]

    rng = random.Random(42)
    base_date = datetime.date(2026, 1, 1)
    sessions: list[Session] = []
    for day in range(num_sessions):
        date_key = (base_date + datetime.timedelta(days=day)).isoformat()
        entries: dict[StudentId, SessionEntry] = {}
        for student in students:
            entry = SessionEntry()
            col = grade_columns[day % len(grade_columns)]
            entry.grades[col.column_id] = round(rng.uniform(1.0, 6.0), 1)
            entry.symbols["beteiligung"] = rng.randint(1, 3)
            entries[student.student_id] = entry
        sessions.append(Session(date=date_key, entries=entries))

    documentation = DocumentationBlock(grade_columns=grade_columns, sessions=sessions)
    return SeatingPlan(
        format_version=4,
        plan_id="perf-bench-synthetic",
        meta=PlanMeta(name="Benchmark (synthetisch)"),
        classroom=classroom,
        documentation=documentation,
    )


# --- Baseline: originalgetreue Kopie der vor dem Fix entfernten Logik ------

def _baseline_latest_grade_value(plan: SeatingPlan, student_id: StudentId, column_id: str) -> str:
    """Wie die entfernte ``_latest_grade_value_for_column`` — sortiert bei jedem Aufruf neu."""
    latest: float | None = None
    for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
        entry = session.entry_for(student_id)
        if entry is None:
            continue
        value = entry.grades.get(column_id)
        if value is None:
            continue
        latest = float(value)
    return "" if latest is None else f"{latest:.2f}"


def run_baseline_latest_grades(plan: SeatingPlan) -> dict[tuple[StudentId, str], str]:
    """Reproduziert den alten O(Schüler x Spalten x Sessions log Sessions)-Pfad."""
    results: dict[tuple[StudentId, str], str] = {}
    for student in plan.classroom.students:
        for col in plan.documentation.grade_columns:
            results[(student.student_id, col.column_id)] = _baseline_latest_grade_value(
                plan, student.student_id, col.column_id
            )
    return results


def run_new_latest_grades(plan: SeatingPlan) -> dict[tuple[StudentId, str], str]:
    """Nutzt die aktuelle Bulk-Berechnung (ein Durchlauf für alle Schüler)."""
    latest = compute_latest_grades_by_student(plan)
    results: dict[tuple[StudentId, str], str] = {}
    for student in plan.classroom.students:
        per_student = latest.get(student.student_id, {})
        for col in plan.documentation.grade_columns:
            raw = per_student.get(col.column_id)
            results[(student.student_id, col.column_id)] = "" if raw is None else f"{raw:.2f}"
    return results


def _baseline_summarize_latest_symbols(plan: SeatingPlan, student_id: StudentId) -> dict[str, int]:
    """Wie die ungeänderte ``summarize_latest_symbols`` — pro Aufruf neu sortieren (Einzelschüler-API)."""
    summary: dict[str, int] = {}
    for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
        entry = session.entry_for(student_id)
        if entry is not None:
            summary.update(entry.symbols)
    return summary


def _baseline_compute_grade_display(plan: SeatingPlan, student_id: StudentId) -> str:
    """Wie die ungeänderte ``compute_grade_display`` — sortiert bei jedem Aufruf neu (Einzelschüler-API)."""
    student = plan.classroom.student_by_id(student_id)
    if student is None or not student.is_named():
        return ""
    cat_by_col = {col.column_id: col.category for col in plan.documentation.grade_columns}
    written_vals: list[float] = []
    sonstige_vals: list[float] = []
    for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
        entry = session.entry_for(student_id)
        if entry is None:
            continue
        for col_id, grade_val in entry.grades.items():
            cat = cat_by_col.get(col_id)
            if cat == "schriftlich":
                written_vals.append(float(grade_val))
            elif cat == "sonstig":
                sonstige_vals.append(float(grade_val))
    if not written_vals and not sonstige_vals:
        return ""
    written_avg = sum(written_vals) / len(written_vals) if written_vals else None
    sonstige_avg = sum(sonstige_vals) / len(sonstige_vals) if sonstige_vals else None
    if written_avg is not None and sonstige_avg is not None:
        w = _round_half_up_to_int(written_avg)
        s = _round_half_up_to_int(sonstige_avg)
        weighting = plan.documentation.weighting
        total = weighting.written_percent + weighting.sonstige_percent
        if total <= 0:
            total = 100
        overall = (w * weighting.written_percent + s * weighting.sonstige_percent) / total
        return f"{_round_half_up_to_two_decimals(overall):.2f}"
    partial = written_avg if written_avg is not None else sonstige_avg
    assert partial is not None
    return f"({_round_half_up_to_int(partial)})"


def run_baseline_full_row_computation(plan: SeatingPlan) -> dict[StudentId, tuple]:
    """Reproduziert die *gesamte* pro-Zeile-Berechnung, wie sie ``_refresh_documentation_table``

    vor dem Fix ausführte: für jeden Schüler einzeln neuestes-Symbol-Update,
    neueste Note je Spalte, sowie die Gesamtnoten-Anzeige — jeweils mit
    eigenem Sessions-Resort statt einer geteilten Vorberechnung.
    """
    results: dict[StudentId, tuple] = {}
    for student in plan.classroom.students:
        summary = _baseline_summarize_latest_symbols(plan, student.student_id)
        grades = tuple(
            _baseline_latest_grade_value(plan, student.student_id, col.column_id)
            for col in plan.documentation.grade_columns
        )
        overall = _baseline_compute_grade_display(plan, student.student_id)
        results[student.student_id] = (summary, grades, overall)
    return results


def run_new_full_row_computation(plan: SeatingPlan) -> dict[StudentId, tuple]:
    """Reproduziert dieselbe pro-Zeile-Berechnung mit den aktuellen Bulk-Funktionen."""
    latest_grades = compute_latest_grades_by_student(plan)
    latest_symbols = summarize_latest_symbols_by_student(plan)
    overall_by_student = compute_grade_display_by_student(plan)
    results: dict[StudentId, tuple] = {}
    for student in plan.classroom.students:
        summary = latest_symbols.get(student.student_id, {})
        per_student_grades = latest_grades.get(student.student_id, {})
        grades = tuple(
            "" if (raw := per_student_grades.get(col.column_id)) is None else f"{raw:.2f}"
            for col in plan.documentation.grade_columns
        )
        overall = overall_by_student.get(student.student_id, "")
        results[student.student_id] = (summary, grades, overall)
    return results


def run_grade_display_baseline(plan: SeatingPlan) -> dict[StudentId, tuple[str, str, str]]:
    """Alte, pro Schüler neu sortierende Gesamtnoten-/Teilnoten-Berechnung (Referenzimplementierung)."""
    valid_written = {c.column_id for c in plan.documentation.grade_columns if c.category == "schriftlich"}
    valid_sonstig = {c.column_id for c in plan.documentation.grade_columns if c.category == "sonstig"}

    def subtotal(student_id: StudentId, valid_cols: set[str]) -> str:
        values: list[float] = []
        for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
            entry = session.entry_for(student_id)
            if entry is None:
                continue
            for col_id, grade_val in entry.grades.items():
                if col_id in valid_cols:
                    values.append(float(grade_val))
        return str(_round_half_up_to_int(sum(values) / len(values))) if values else ""

    return {
        student.student_id: (
            _baseline_compute_grade_display(plan, student.student_id),
            subtotal(student.student_id, valid_written) if valid_written else "",
            subtotal(student.student_id, valid_sonstig) if valid_sonstig else "",
        )
        for student in plan.classroom.students
    }


def run_grade_display_new(plan: SeatingPlan) -> dict[StudentId, tuple[str, str, str]]:
    """Aktuelle Bulk-Berechnung von Gesamtnote + beiden Teilnoten für alle Schüler.

    Ruft ``collect_grade_value_lists_by_student`` genau einmal auf und reicht
    das Ergebnis an alle drei Anzeige-Funktionen weiter — wie es
    ``_refresh_documentation_table`` tatsächlich tut.
    """
    value_lists = collect_grade_value_lists_by_student(plan)
    overall = compute_grade_display_by_student(plan, value_lists=value_lists)
    written = compute_grade_subtotal_display_by_student(plan, "schriftlich", value_lists=value_lists)
    sonstig = compute_grade_subtotal_display_by_student(plan, "sonstig", value_lists=value_lists)
    return {
        student.student_id: (
            overall.get(student.student_id, ""),
            written.get(student.student_id, ""),
            sonstig.get(student.student_id, ""),
        )
        for student in plan.classroom.students
    }


def _timeit(fn, repeats: int) -> float:
    """Misst die durchschnittliche Laufzeit eines Aufrufs über *repeats* Wiederholungen."""
    start = time.perf_counter()
    for _ in range(repeats):
        fn()
    return (time.perf_counter() - start) / repeats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--students", type=int, default=25)
    parser.add_argument("--sessions", type=int, default=40)
    parser.add_argument("--grade-columns", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    print(f"Synthetischer Plan: {args.students} Schüler, {args.sessions} Sessions, {args.grade_columns} Notenspalten")
    plan = build_synthetic_plan(args.students, args.sessions, args.grade_columns)

    baseline_result = run_baseline_latest_grades(plan)
    new_result = run_new_latest_grades(plan)
    grades_match = baseline_result == new_result
    print(f"Korrektheit (letzte Note je Spalte, alt vs. neu): {'OK' if grades_match else 'ABWEICHUNG!'}")

    baseline_row_result = run_baseline_full_row_computation(plan)
    new_row_result = run_new_full_row_computation(plan)
    rows_match = baseline_row_result == new_row_result
    print(f"Korrektheit (komplette Zeilenberechnung, alt vs. neu): {'OK' if rows_match else 'ABWEICHUNG!'}")

    baseline_row_time = _timeit(lambda: run_baseline_full_row_computation(plan), args.repeats)
    new_row_time = _timeit(lambda: run_new_full_row_computation(plan), args.repeats)
    row_speedup = baseline_row_time / new_row_time if new_row_time > 0 else float("inf")
    print(
        "Komplette Zeilenberechnung (Kernstück von _refresh_documentation_table) — "
        f"alt: {baseline_row_time * 1000:.2f} ms  neu: {new_row_time * 1000:.2f} ms  (×{row_speedup:.1f})"
    )

    baseline_time = _timeit(lambda: run_baseline_latest_grades(plan), args.repeats)
    new_time = _timeit(lambda: run_new_latest_grades(plan), args.repeats)
    speedup = baseline_time / new_time if new_time > 0 else float("inf")
    print(f"Letzte Note je Spalte — alt: {baseline_time * 1000:.2f} ms  neu: {new_time * 1000:.2f} ms  (×{speedup:.1f})")

    display_baseline_result = run_grade_display_baseline(plan)
    display_new_result = run_grade_display_new(plan)
    display_match = display_baseline_result == display_new_result
    print(f"Korrektheit (Gesamt-/Teilnoten-Anzeige, alt vs. neu): {'OK' if display_match else 'ABWEICHUNG!'}")

    display_baseline_time = _timeit(lambda: run_grade_display_baseline(plan), args.repeats)
    display_new_time = _timeit(lambda: run_grade_display_new(plan), args.repeats)
    display_speedup = display_baseline_time / display_new_time if display_new_time > 0 else float("inf")
    print(
        "Gesamt-/Teilnoten-Anzeige (alle Schüler) — "
        f"alt: {display_baseline_time * 1000:.2f} ms  neu: {display_new_time * 1000:.2f} ms  (×{display_speedup:.1f})"
    )

    treeview_ok = check_treeview_item_update_matches_reinsert()
    print(f"Treeview-Diff-Update-Mechanismus (item() vs. delete+insert): {'OK' if treeview_ok else 'ABWEICHUNG!'}")

    old_calls, new_calls = count_tcl_calls_for_single_cell_edit(args.students)
    print(
        f"Tk-Aufrufe bei EINER geänderten Zeile ({args.students} Zeilen gesamt) — "
        f"alt: {old_calls} (immer alle Zeilen löschen+neu einfügen)  "
        f"neu: {new_calls} (nur die geänderte Zeile)"
    )

    if not grades_match or not rows_match or not display_match or not treeview_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
