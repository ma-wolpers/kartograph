"""Tk-Test: Sitzplan-Vorschau-Dialog öffnet bzw. aktualisiert genau eine Vorschau mit Farbrahmen.

Echtes Hauptfenster mit synthetischem Plan (erfundene Namen, isoliertes
``APPDATA``, siehe ``app.tools.isolated_window``). Abgesichert:
- Erstes Öffnen: Dialog mit Standardvorbelegung, Enter öffnet die Vorschau.
- Erneutes Öffnen: Dialog ist mit den Einstellungen der offenen Vorschau
  vorbelegt, Enter aktualisiert dieselbe Vorschau (kein zweites Fenster);
  nicht mehr vergebene Farben fallen aus der Auswahl.
- Rendering: gestaffelte Ringe in Palettenfarben, Namen über den Rahmen.
"""

from __future__ import annotations

import pytest

from app.adapters.gui.main_window_constants import COLOR_MARKER_PALETTE
from app.core.domain.color_order import palette_by_key
from app.core.domain.preview_color_frames import PreviewOptions
from app.core.domain.seat_orientation import TEACHER_BOTTOM, TEACHER_TOP
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.testing.keys import press_key
from app.tools.isolated_window import open_isolated_window

HEX = {key: hex_color for key, (_label, hex_color) in palette_by_key(COLOR_MARKER_PALETTE).items()}


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    """Hauptfenster mit einem Plan, dessen erster Schüler die Farben gelb (1) und rot (3) trägt."""
    plan = build_synthetic_plan(3, 1, 0)
    plan.classroom.students[0].diagnostic.color_tags = ["rot", "gelb"]
    app, close = open_isolated_window(tmp_path_factory.mktemp("kartograph_preview"), plan)
    yield app
    app._close_sitzplan_popup()
    close()


def _confirm_preview_dialog(app) -> None:
    """Öffnet den Vorschau-Dialog über den Menü-Einstieg und bestätigt ihn mit Enter."""
    dialogs = []
    original = app._create_overlay_dialog
    app._create_overlay_dialog = lambda *a, **k: dialogs.append(original(*a, **k)) or dialogs[-1]
    try:
        app.open_sitzplan_popup()
    finally:
        del app._create_overlay_dialog
    app.tk_root.update()
    assert press_key(dialogs[0], "Return") is True
    app.tk_root.update()
    assert not dialogs[0].winfo_exists()


def _preview_windows(app) -> list:
    """Alle offenen Toplevels mit dem Titel der Vorschau."""
    return [w for w in app.tk_root.winfo_children() if getattr(w, "title", None) and w.winfo_class() == "Toplevel" and w.title() == "Sitzplan-Vorschau"]


def test_first_open_uses_defaults_and_opens_one_preview(window):
    """Ohne offene Vorschau: Lehrertisch oben, keine Farben, Staffelung an."""
    _confirm_preview_dialog(window)
    popup = window._live_sitzplan_popup()
    assert popup is not None
    assert popup.options == PreviewOptions()
    assert popup.options.orientation == TEACHER_TOP
    assert len(_preview_windows(window)) == 1


def test_reopen_is_prefilled_and_updates_the_same_preview(window):
    """Vorbelegung = Einstellungen der offenen Vorschau; Bestätigen öffnet kein zweites Fenster."""
    popup = window._live_sitzplan_popup()
    assert popup is not None
    popup.set_options(PreviewOptions(TEACHER_BOTTOM, frozenset({"gelb", "orange"}), False))

    _confirm_preview_dialog(window)

    assert window._live_sitzplan_popup() is popup
    # "orange" ist im Plan nicht vergeben und fällt deshalb aus der Auswahl.
    assert popup.options == PreviewOptions(TEACHER_BOTTOM, frozenset({"gelb"}), False)
    assert len(_preview_windows(window)) == 1


def test_staggered_rings_are_drawn_in_palette_colors_below_names(window):
    """Gestaffelt: rot (3) außen, gelb (1) innen; der Name liegt über allen Rahmen."""
    popup = window._live_sitzplan_popup()
    popup.set_options(PreviewOptions(TEACHER_TOP, frozenset({"gelb", "rot"}), True))
    window.tk_root.update()
    canvas = popup._canvas
    items = canvas.find_all()
    outlines = [canvas.itemcget(i, "outline") for i in items if canvas.type(i) == "polygon" and not canvas.itemcget(i, "fill")]
    assert outlines == [HEX["rot"], HEX["gelb"]]

    last_ring = max(i for i in items if canvas.type(i) == "polygon")
    texts = [i for i in items if canvas.type(i) == "text"]
    assert texts and min(texts) > last_ring


def test_unstaggered_draws_only_the_highest_color(window):
    """Ohne Staffelung nur ein Ring in der höchsten gewählten Farbe."""
    popup = window._live_sitzplan_popup()
    popup.set_options(PreviewOptions(TEACHER_TOP, frozenset({"gelb", "rot"}), False))
    window.tk_root.update()
    canvas = popup._canvas
    outlines = [canvas.itemcget(i, "outline") for i in canvas.find_all() if canvas.type(i) == "polygon" and not canvas.itemcget(i, "fill")]
    assert outlines == [HEX["rot"]]
