"""Perf-Benchmark + Regressionscheck für die Dokumentationstabelle (v4).

Vergleicht die pro Schüler neu scannende Berechnung gegen die aktuelle
Implementierung (ein Durchlauf für alle Schüler gleichzeitig, siehe
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

from app.core.domain.grade_scale import DEFAULT_SCALE_ID, scale_for
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
from app.core.usecases.v4.grade_usecases import (
    collect_grade_value_lists_by_student,
    compute_grade_display,
    compute_grade_display_by_student,
    compute_grade_subtotal_display,
    compute_grade_subtotal_display_by_student,
)
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols_by_student


# Wertebereich der Zufallsnoten aus der Skalen-Registry (SSOT), nicht hart kodiert.
_GRADES = scale_for(DEFAULT_SCALE_ID)


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
            entry.symbols["beteiligung"] = rng.randint(1, 3)
            entries[student.student_id] = entry
        sessions.append(Session(date=date_key, entries=entries))

    grades = {
        student.student_id: {
            col.column_id: round(rng.uniform(_GRADES.min_value, _GRADES.max_value), 1) for col in grade_columns
        }
        for student in students
    }
    documentation = DocumentationBlock(grade_columns=grade_columns, sessions=sessions, grades=grades)
    return SeatingPlan(
        format_version=4,
        plan_id="perf-bench-synthetic",
        meta=PlanMeta(name="Benchmark (synthetisch)"),
        classroom=classroom,
        documentation=documentation,
    )


# --- Baseline: originalgetreue Kopie der vor dem Fix entfernten Logik ------
# (nur Funktionen, die im Produktivcode nicht mehr existieren; noch lebende
# Logik wie die Notenformel wird direkt aufgerufen, nicht kopiert)

def _baseline_summarize_latest_symbols(plan: SeatingPlan, student_id: StudentId) -> dict[str, int]:
    """Wie die ungeänderte ``summarize_latest_symbols`` — pro Aufruf neu sortieren (Einzelschüler-API)."""
    summary: dict[str, int] = {}
    for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
        entry = session.entry_for(student_id)
        if entry is not None:
            summary.update(entry.symbols)
    return summary


def run_baseline_full_row_computation(plan: SeatingPlan) -> dict[StudentId, tuple]:
    """Reproduziert die *gesamte* pro-Zeile-Berechnung, wie sie ``_refresh_documentation_table``

    vor dem Fix ausführte: für jeden Schüler einzeln neuestes-Symbol-Update,
    Note je Spalte sowie die Gesamtnoten-Anzeige — mit eigenem Sessions-Resort
    statt einer geteilten Vorberechnung.
    """
    results: dict[StudentId, tuple] = {}
    for student in plan.classroom.students:
        summary = _baseline_summarize_latest_symbols(plan, student.student_id)
        grades = tuple(
            "" if (raw := plan.documentation.grade_of(student.student_id, col.column_id)) is None else f"{raw:.2f}"
            for col in plan.documentation.grade_columns
        )
        overall = compute_grade_display(plan, student.student_id)
        results[student.student_id] = (summary, grades, overall)
    return results


def run_new_full_row_computation(plan: SeatingPlan) -> dict[StudentId, tuple]:
    """Reproduziert dieselbe pro-Zeile-Berechnung mit den aktuellen Bulk-Funktionen."""
    grades_by_student = plan.documentation.grades
    latest_symbols = summarize_latest_symbols_by_student(plan)
    overall_by_student = compute_grade_display_by_student(plan)
    results: dict[StudentId, tuple] = {}
    for student in plan.classroom.students:
        summary = latest_symbols.get(student.student_id, {})
        per_student_grades = grades_by_student.get(student.student_id, {})
        grades = tuple(
            "" if (raw := per_student_grades.get(col.column_id)) is None else f"{raw:.2f}"
            for col in plan.documentation.grade_columns
        )
        overall = overall_by_student.get(student.student_id, "")
        results[student.student_id] = (summary, grades, overall)
    return results


def run_grade_display_baseline(plan: SeatingPlan) -> dict[StudentId, tuple[str, str, str]]:
    """Pro Schüler einzeln scannende Gesamtnoten-/Teilnoten-Berechnung (Referenzpfad).

    Nutzt die echten Einzelschüler-Usecases statt einer eigenen Kopie der
    Notenformel (SSOT): gemessen wird so nur der Unterschied "jeder Schüler
    scannt alle Sessions" gegenüber dem geteilten Bulk-Durchlauf.
    """
    return {
        student.student_id: (
            compute_grade_display(plan, student.student_id),
            compute_grade_subtotal_display(plan, student.student_id, "schriftlich"),
            compute_grade_subtotal_display(plan, student.student_id, "sonstig"),
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

    # Tk-seitige Kosten (Doku-Tabelle als bw-gui DataGrid) misst perf_bench_gui_nav am echten Fenster.
    if not rows_match or not display_match:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
