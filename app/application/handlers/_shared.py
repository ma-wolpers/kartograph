"""Interne Hilfsfunktionen für die Handler-Schicht."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Hashable
from functools import wraps
from pathlib import Path
from typing import TypeVar

from app.application.app_state import AppState, PlanListEntry
from app.application.handler_context import HandlerContext
from app.application.plan_listing import build_plan_list
from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.settings import resolve_plans_dir
from app.core.usecases.v4.color_usecases import drop_unused_palette_entries
from app.core.usecases.v4.tablegroup_usecases import apply_normalized_tablegroups

IntentT = TypeVar("IntentT")


def requires_open_plan(
    handler: Callable[[IntentT, AppState, HandlerContext], AppState],
) -> Callable[[IntentT, AppState, HandlerContext], AppState]:
    """Lässt einen Handler nur mit geöffnetem Plan laufen; sonst bleibt der Zustand unverändert.

    Args:
        handler: Handler, der einen geöffneten Plan voraussetzt.

    Returns:
        Der abgesicherte Handler.
    """

    @wraps(handler)
    def guarded(intent: IntentT, state: AppState, ctx: HandlerContext) -> AppState:
        """Prüft den geöffneten Plan und ruft erst dann den eigentlichen Handler auf."""
        if state.current_plan is None or state.current_plan_path is None:
            return state
        return handler(intent, state, ctx)

    return guarded


def _record_and_save(
    plan: SeatingPlan,
    path: Path,
    ctx: HandlerContext,
    *,
    merge_key: Hashable | None = None,
) -> None:
    """Schreibt *plan* als eigenen Undo-Schritt in die History und persistiert ihn unter *path*.

    Vorher werden die Tischgruppen von *plan* in-place aus der aktuellen
    Sitznachbarschaft neu berechnet (``apply_normalized_tablegroups``). Weil
    jeder planverändernde Handler hier durchläuft, gilt die Invariante
    "Tischgruppen passen zur Sitznachbarschaft" für jeden übernommenen
    Zustand: Editor-Raster, Sitzplan-Vorschau und Exporte sehen dieselbe
    Geometrie, History und Datei ebenso. In-place ist sicher, weil die
    Handler hier das frisch erzeugte Ergebnis eines Use-Cases übergeben.
    Ein Use-Case, der im No-op-Fall den Eingabeplan zurückgibt, ist ebenfalls
    unkritisch: Der ist bereits normalisiert, die Neuberechnung idempotent.
    Ebenso werden Bedeutungen nicht mehr getragener Farben verworfen
    (``drop_unused_palette_entries``, gleiche In-place-Begründung).

    Die History-Aufzeichnung ist immer synchron (unverändert) — sie ist die
    Grundlage für Undo/Redo und muss bei jedem Edit sofort aktuell sein.
    Das eigentliche Schreiben auf die Festplatte kann dagegen über
    ``ctx.plan_save_scheduler`` an einen debounced GUI-Hook delegiert werden
    (s. ``HandlerContext.plan_save_scheduler``, ``_mixin_plan_save.py``) —
    ohne GUI (z. B. in Tests) bleibt das Verhalten unverändert synchron.

    Args:
        plan: Neuer Planzustand.
        path: Zieldatei für die Persistenz.
        ctx: Handler-Kontext mit Zugriff auf History und Repository.
        merge_key: An ``PlanHistory.record`` durchgereicht; nur für laufende Texteingaben.
    """
    apply_normalized_tablegroups(plan)
    drop_unused_palette_entries(plan)
    ctx.history.record(plan, merge_key=merge_key)
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
        can_undo=ctx.history.can_undo,
        can_redo=ctx.history.can_redo,
        status_message=status,
    )


def _commit_plan_change(
    state: AppState,
    ctx: HandlerContext,
    plan: SeatingPlan,
    *,
    merge_key: Hashable | None = None,
    status: str = "",
) -> AppState:
    """Nimmt eine Planänderung auf, speichert sie und überträgt sie in den AppState.

    Args:
        state: Bisheriger AppState mit geöffnetem Plan.
        ctx: Handler-Kontext (History, Repository).
        plan: Neuer Planzustand.
        merge_key: An ``_record_and_save`` durchgereicht.
        status: Statusmeldung für die GUI.

    Returns:
        Neuer AppState mit dem geänderten Plan.
    """
    _record_and_save(plan, state.current_plan_path, ctx, merge_key=merge_key)
    return _with_plan(state, plan, ctx, status=status)


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
