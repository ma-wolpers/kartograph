"""Zoom-Intents wirken je nach Oberfläche: Raster → Zellgröße, Doku-Tabelle → Spaltenbreiten."""

import dataclasses

from app.application.app_state import AppState, EditorSurface
from app.application.handlers.view_handlers import (
    DEFAULT_CELL_SIZE,
    MAX_DOCS_WIDTH_SCALE,
    MIN_DOCS_WIDTH_SCALE,
    handle_reset_view,
    handle_zoom_in,
    handle_zoom_out,
)
from app.core.intents.view_intents import ResetViewIntent, ZoomInIntent, ZoomOutIntent

DOCS = dataclasses.replace(AppState(), editor_surface=EditorSurface.DOCUMENTATION)


def test_docs_surface_zooms_column_widths_only():
    state = handle_zoom_in(ZoomInIntent(), DOCS, None)
    assert state.docs_width_scale == 1.1 and state.cell_size == DOCS.cell_size
    state = handle_zoom_out(ZoomOutIntent(), handle_zoom_out(ZoomOutIntent(), state, None), None)
    assert state.docs_width_scale == 0.9
    assert handle_reset_view(ResetViewIntent(), state, None).docs_width_scale == 1.0


def test_docs_width_scale_is_clamped():
    state = DOCS
    for _ in range(30):
        state = handle_zoom_in(ZoomInIntent(), state, None)
    assert state.docs_width_scale == MAX_DOCS_WIDTH_SCALE
    for _ in range(30):
        state = handle_zoom_out(ZoomOutIntent(), state, None)
    assert state.docs_width_scale == MIN_DOCS_WIDTH_SCALE


def test_grid_surface_keeps_zooming_cells():
    state = handle_zoom_in(ZoomInIntent(), AppState(), None)
    assert state.cell_size > DEFAULT_CELL_SIZE and state.docs_width_scale == 1.0
