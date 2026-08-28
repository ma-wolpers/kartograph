"""Interne Hilfsfunktionen für die Handler-Schicht."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from app.application.app_state import AppState, PlanListEntry
from app.application.handler_context import HandlerContext
from app.application.plan_listing import build_plan_list
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

    Die History-Aufzeichnung ist immer synchron (unverändert) — sie ist die
    Grundlage für Undo/Redo und muss bei jedem Edit sofort aktuell sein.
    Das eigentliche Schreiben auf die Festplatte kann dagegen über
    ``ctx.plan_save_scheduler`` an einen debounced GUI-Hook delegiert werden
    (s. ``HandlerContext.plan_save_scheduler``, ``_mixin_plan_save.py``) —
    ohne GUI (z. B. in Tests) bleibt das Verhalten unverändert synchron.

    Args:
        plan: Neuer Planzustand.
        path: Zieldatei für die Persistenz.
        action_kind: Kurzbezeichner der Aktion für den History-Eintrag (z. B. ``"student.move"``).
        ctx: Handler-Kontext mit Zugriff auf History und Repository.
    """
    ctx.history.record(plan, action_kind)
    if ctx.plan_save_scheduler is not None:
        ctx.plan_save_scheduler(plan, path)
    else:
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
        return build_plan_list(ctx.plan_repository, plans_dir, include_archived=state.settings.show_archived_plans)
    except Exception:
        return []
