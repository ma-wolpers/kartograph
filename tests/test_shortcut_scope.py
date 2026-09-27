"""Tests für den fachlichen Shortcut-Scope (app/application/shortcut_scope.py)."""

from __future__ import annotations

import dataclasses

from app.application.app_state import AppState, InteractionMode
from app.application.shortcut_scope import (
    NON_PREVIEW_SHORTCUT_MODES,
    PREVIEW_SHORTCUT_MODES,
    is_preview_shortcut_scope,
)
from app.tools.perf_bench_docs_table import build_synthetic_plan


def test_every_interaction_mode_is_assigned_to_exactly_one_scope():
    # Ein neuer InteractionMode muss bewusst einem Shortcut-Scope zugeordnet werden.
    assert PREVIEW_SHORTCUT_MODES | NON_PREVIEW_SHORTCUT_MODES == set(InteractionMode)
    assert not PREVIEW_SHORTCUT_MODES & NON_PREVIEW_SHORTCUT_MODES


def test_preview_scope_requires_open_plan_and_editor_mode():
    plan = build_synthetic_plan(num_students=2, num_sessions=0, num_grade_columns=0)
    base = AppState()
    assert not is_preview_shortcut_scope(base)
    assert is_preview_shortcut_scope(dataclasses.replace(base, current_plan=plan, interaction_mode=InteractionMode.GRID))
    assert is_preview_shortcut_scope(
        dataclasses.replace(base, current_plan=plan, interaction_mode=InteractionMode.NAME_EDIT)
    )
    assert not is_preview_shortcut_scope(dataclasses.replace(base, current_plan=plan, interaction_mode=InteractionMode.LIST))
    # Inkonsistenter Zwischenzustand: Editor-Modus ohne Plan schaltet keine Editor-Kürzel frei.
    assert not is_preview_shortcut_scope(dataclasses.replace(base, interaction_mode=InteractionMode.GRID))
