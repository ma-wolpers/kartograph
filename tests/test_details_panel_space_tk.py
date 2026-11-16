"""Tk-Test: Das Details-Panel zeigt immer alle Details, auch bei vielen Symbolen.

Eine Person trägt alle Diagnosesymbole (Stufe 3) und alle Farbpunkte mit
Bedeutung -- die Legenden werden dadurch lang. Für jede Andock-Position
(links, rechts, unten) gilt:

* das Notizfeld ist erreichbar: sichtbar oder nach Scrollen des Panels sichtbar,
* Symbol-Kürzel-Leiste und Namensfelder sind nicht rechts abgeschnitten,
* unten angedockt bleibt das Raster sichtbar (das Panel nimmt nicht alles).

Echtes Hauptfenster (``open_isolated_window``, temporärer Workspace,
synthetischer Plan -- keine echten Daten).
"""

from __future__ import annotations

import json

import pytest

from app.adapters.gui.main_window_constants import COLOR_MARKER_PALETTE
from app.core.domain.models_v4 import PaletteEntry
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.infrastructure.symbol_config_loader import DEFAULT_SYMBOLS_PATH
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan


def _plan_with_crowded_student():
    """Synthetischer Plan; die erste Person trägt alle Diagnosesymbole und Farben."""
    plan = build_synthetic_plan(3, 1, 0)
    symbols = json.loads(DEFAULT_SYMBOLS_PATH.read_text(encoding="utf-8"))["symbols"]
    diagnostic = [item["meaning"] for item in symbols if item.get("role") != "documentation_only"]
    student = plan.classroom.students[0]
    student.diagnostic.symbols = {meaning: 3 for meaning in diagnostic}
    student.diagnostic.color_tags = [color_key for _key, color_key, _label, _hex in COLOR_MARKER_PALETTE]
    plan.color_palette = {
        color_key: PaletteEntry(meaning=f"Bedeutung {label} mit etwas längerem Erklärtext")
        for _key, color_key, label, _hex in COLOR_MARKER_PALETTE
    }
    return plan


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    app, close = open_isolated_window(tmp_path_factory.mktemp("details_space"), _plan_with_crowded_student())
    app.tk_root.geometry("1100x650+0+0")
    app._controller.dispatch(SetEditorSurfaceIntent(surface="grid"))
    student = app.current_plan.classroom.students[0]
    app._set_selection_single(student.seat.x, student.seat.y)
    app._reveal_details(student.seat.x, student.seat.y)
    app.tk_root.update()
    yield app
    close()


def _dock(app, position: str) -> None:
    app.details_overlay_position_var.set(position)
    app._on_details_overlay_position_changed()
    for _ in range(3):
        app.tk_root.update()


def _right_edge(widget) -> int:
    return widget.winfo_rootx() + widget.winfo_width()


def _bottom_edge(widget) -> int:
    return widget.winfo_rooty() + widget.winfo_height()


@pytest.mark.parametrize("position", ["left", "right", "bottom"])
def test_notes_field_is_reachable(window, position):
    _dock(window, position)
    scroll = getattr(window, "details_scroll", None)
    if scroll is not None:
        scroll.canvas.yview_moveto(1.0)
        window.tk_root.update()

    notes = window.notes_field.text
    assert notes.winfo_ismapped()
    assert notes.winfo_height() > 10
    assert _bottom_edge(notes) <= _bottom_edge(window.details_container)
    assert _bottom_edge(notes) <= _bottom_edge(window.tk_root)


@pytest.mark.parametrize("position", ["left", "right", "bottom"])
def test_shortcut_badges_and_name_fields_are_not_clipped(window, position):
    _dock(window, position)
    limit = _right_edge(window.details_container)
    badges = window._symbol_shortcuts_bar.winfo_children()
    assert badges
    for widget in [*badges, window.name_entry, window.last_name_entry, window.nickname_entry]:
        assert _right_edge(widget) <= limit, widget


def test_bottom_dock_leaves_room_for_the_grid(window):
    _dock(window, "bottom")
    assert window.grid_stack.winfo_height() >= window.tk_root.winfo_height() // 3
