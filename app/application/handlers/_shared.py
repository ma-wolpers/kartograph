"""Interne Hilfsfunktionen für die Handler-Schicht."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from app.application.app_state import AppState, PlanListEntry
from app.application.handler_context import HandlerContext
from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.settings import resolve_plans_dir


def _can_undo(ctx: HandlerContext) -> bool:
    """Prüft, ob mehr als der initiale History-Zustand vorhanden ist (also rückgängig machbar).

    Args:
        ctx: Handler-Kontext mit Zugriff auf die ``PlanHistory``.
    """
    return len(ctx.history._states) > 1  # noqa: SLF001


def _can_redo(ctx: HandlerContext) -> bool:
    """Prüft, ob die History bereits rückgängig gemachte Zustände zum Wiederholen vorhält.

    Args:
        ctx: Handler-Kontext mit Zugriff auf die ``PlanHistory``.
    """
    return bool(ctx.history._redo_states)  # noqa: SLF001


def _record_and_save(
    plan: SeatingPlan,
    path: Path,
    action_kind: str,
    ctx: HandlerContext,
) -> None:
    """Schreibt *plan* in die History (unter *action_kind*) und persistiert ihn unter *path*.

    Args:
        plan: Neuer Planzustand.
        path: Zieldatei für die Persistenz.
        action_kind: Kurzbezeichner der Aktion für den History-Eintrag (z. B. ``"student.move"``).
        ctx: Handler-Kontext mit Zugriff auf History und Repository.
    """
    ctx.history.record(plan, action_kind)
    ctx.plan_repository.save_plan(plan, path)


def _with_plan(
    state: AppState,
    plan: SeatingPlan,
    ctx: HandlerContext,
    *,
    status: str = "",
) -> AppState:
    """Gibt einen neuen AppState mit dem aktualisierten Plan zurück.

    Args:
        state: Bisheriger AppState.
        plan: Neuer Planzustand, der in den State übernommen wird.
        ctx: Handler-Kontext, aus dem ``can_undo``/``can_redo`` abgeleitet werden.
        status: Statusmeldung für die GUI.
    """
    return dataclasses.replace(
        state,
        current_plan=plan,
        can_undo=_can_undo(ctx),
        can_redo=_can_redo(ctx),
        status_message=status,
    )


def _refresh_plan_list(state: AppState, ctx: HandlerContext) -> list[PlanListEntry]:
    """Liest alle Pläne aus dem konfigurierten Plan-Ordner neu ein; gibt bei Fehlern eine leere Liste zurück.

    Args:
        state: Aktueller AppState (liefert den konfigurierten Plan-Ordner).
        ctx: Handler-Kontext mit Zugriff auf Repository und Fallback-Verzeichnis.
    """
    plans_dir = resolve_plans_dir(state.settings.plans_dir, ctx.default_plans_dir)
    try:
        return [
            PlanListEntry(
                path=p,
                name=plan.meta.name,
                student_count=len(plan.classroom.students),
            )
            for p, plan in ctx.plan_repository.list_plans(plans_dir)
        ]
    except Exception:
        return []
