"""Gemeinsamer Helfer zum Zusammensetzen der anzuzeigenden Planliste.

Es gibt zwei Stellen, die aus Repository-Ergebnissen eine ``PlanListEntry``-Liste
bauen müssen: den Intent-Handler-Pfad (``handlers._shared._refresh_plan_list``)
und den direkten GUI-Refresh (``PlanListMixin.refresh_plan_list``, u. a. beim
App-Start). Damit "normale + optional archivierte Pläne zusammenführen" nicht an
zwei Stellen unabhängig implementiert wird (Drift-Risiko), lebt diese Logik hier
als einzige, reine Funktion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.application.app_state import PlanListEntry
from app.core.domain.models_v4 import SeatingPlan


class _PlanRepository(Protocol):
    """Minimaler Vertrag, den ``build_plan_list`` von einem Plan-Repository braucht."""

    def list_plans(self, plans_dir: Path) -> list[tuple[Path, SeatingPlan]]: ...

    def list_archived_plans(self, plans_dir: Path) -> list[tuple[Path, SeatingPlan]]: ...


def build_plan_list(
    plan_repository: _PlanRepository, plans_dir: Path, *, include_archived: bool
) -> list[PlanListEntry]:
    """Baut die anzuzeigende Planliste aus normalen und optional archivierten Plänen.

    Einzige Stelle im Projekt, die Repository-Ergebnisse (normal + Archiv) zu
    ``PlanListEntry``-Objekten zusammenführt.

    Args:
        plan_repository: Repository mit ``list_plans``/``list_archived_plans``.
        plans_dir: Plan-Ordner.
        include_archived: Ob archivierte Pläne (aus dem ``ALT``-Unterordner) mit
            aufgenommen werden.

    Returns:
        Normale Pläne zuerst (Repository-Sortierung), danach — falls
        *include_archived* — archivierte Pläne (dieselbe Sortierung,
        ``is_archived=True``).
    """
    entries = [
        PlanListEntry(path=p, name=plan.meta.name, student_count=len(plan.classroom.students))
        for p, plan in plan_repository.list_plans(plans_dir)
    ]
    if include_archived:
        entries += [
            PlanListEntry(
                path=p, name=plan.meta.name, student_count=len(plan.classroom.students), is_archived=True
            )
            for p, plan in plan_repository.list_archived_plans(plans_dir)
        ]
    return entries
