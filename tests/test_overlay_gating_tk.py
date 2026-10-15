"""Charakterisierung: frühere Popup-Registry + Toplevel-Scan gegen den bw-gui-Overlay-Stack (echtes Tk).

Bis 2026-10-15 führte Kartograph eine ``PopupPolicyRegistry``: Dialoge meldeten sich per
``_track_popup_window`` an (Export-/Eingabedialoge und Tischgruppen-Overlay modal;
Snapshots, Symbol-Verwaltung, Shortcut-Debug als ``dialog.non_blocking``), und vor jeder
Prüfung ergänzte ein Scan jedes sichtbare direkte Kind-Toplevel des Hauptfensters --
Menü-Popups als ``dialog.non_blocking``, alles andere (z. B. die Sitzplan-Vorschau) als
``dialog.modal`` -- bzw. entfernte nicht mehr sichtbare. Daraus kamen die Kürzelsperre
(``has_mode_blocking_popup``) und das Escape-Ziel (``active_popup``).

:class:`_FormerRegistry` konserviert diesen Ablauf. Jetzt liefern
``ShortcutMixin._shortcut_dialog_open`` (``blocking()``, Menüs sperren nicht) und
``bw_gui.runtime.topmost_window`` beides; für jede Popup-Art und Kombinationen müssen alt
und neu übereinstimmen. Bewusste Änderung (Entscheidung 2026-10-15): die Sitzplan-Vorschau
zählte der Scan als Dialog, sie ist jetzt ein Werkzeugfenster und sperrt nicht mehr.
Unbeobachtbare Abweichung: modale Dialoge **in** einem anderen Fenster
(Snapshot-Löschen) zählte der Scan nicht mit -- sie halten aber ``grab_set``, das
Hauptfenster bekommt solange keine Tasten, die Abweichung ist nicht beobachtbar.
Nur synthetische Fenster, keine Klassendaten.
"""

from __future__ import annotations

import tkinter
from types import SimpleNamespace

import pytest

from app.adapters.gui._mixin_popup import PopupMixin
from app.adapters.gui._mixin_shortcuts import ShortcutMixin
from bw_gui.menu.custom_menu_bar import CustomMenuBar
from bw_gui.menu.menu_types import MenuItem
from bw_gui.runtime import create_root, topmost_window, ui
from bw_gui.runtime.overlay_stack import unregistered_visible_toplevels


class _FormerRegistry:
    """Referenz: frühere Registry (Öffnungsreihenfolge) + Scan; Menü-Popups nicht sperrend."""

    def __init__(self, root):
        self.root = root
        self.stack: list[tuple[str, bool]] = []  # (popup_id, blocks)

    def track(self, window, *, blocks: bool = True) -> None:
        if all(pid != str(window) for pid, _ in self.stack):
            self.stack.append((str(window), blocks))

    def sync(self) -> None:
        visible = set()
        for child in self.root.winfo_children():
            if not isinstance(child, ui.Toplevel) or str(child.state()).lower() == "withdrawn":
                continue
            visible.add(str(child))
            self.track(child, blocks=not bool(getattr(child, "_bw_menu_popup", False)))
        self.stack = [(pid, blocks) for pid, blocks in self.stack if pid in visible]

    def dialog_open(self) -> bool:
        self.sync()
        return any(blocks for _pid, blocks in self.stack)

    def escape_target(self) -> str | None:
        self.sync()
        return self.stack[-1][0] if self.stack else None


@pytest.fixture(scope="module")
def root():
    """Sichtbarer Root (transiente Popups eines versteckten Masters blieben versteckt)."""
    for attempt in range(3):
        try:
            instance = create_root()
            break
        except tkinter.TclError as exc:
            if not any(m in str(exc) for m in ("usable", "tcl_findLibrary", "init.tcl")) or attempt == 2:
                raise
    instance.geometry("300x200+30+30")
    instance.update()
    yield instance
    instance.destroy()


@pytest.fixture
def scene(root):
    host = SimpleNamespace(tk_root=root)
    former = _FormerRegistry(root)
    opened: list[object] = []

    class Scene:
        def modal(self, *, tracked: bool = True, parent=None):
            """Export-/Eingabedialog, Tischgruppen-Overlay (getrackt) bzw. nur gescannter Dialog."""
            window = ui.Toplevel(parent or root)
            PopupMixin._register_popup_window(host, window)
            if tracked:
                former.track(window)
            opened.append(window)
            return window

        def tool_window(self):
            """Snapshots / Symbol-Verwaltung / Shortcut-Debug."""
            window = ui.Toplevel(root)
            PopupMixin._register_popup_window(host, window, blocking_shortcuts=False)
            former.track(window, blocks=False)
            opened.append(window)
            return window

        def menu(self):
            bar = CustomMenuBar(root, (), theme_key="mono_day")
            anchor = ui.Frame(root, width=40, height=20)
            anchor.place(x=10, y=10)
            root.update_idletasks()
            # Fokus-Watchdog für die Szene aussetzen (sonst schliesst er das Popup, sobald
            # Testfenster den Fokus zurückholen; wie bw-gui test_menu_popup_placement).
            suspended = bar._focus_watchdog_suspended()
            suspended.__enter__()
            bar.open_popup(anchor, (MenuItem(type="command", label="Eins"),), 0, "datei")
            opened.append((bar, anchor, suspended))
            return bar._popup_stack[0]

        def root_widget(self):
            return root

        def keep(self, window):
            opened.append(window)

        def new(self):
            root.update()
            target = topmost_window(root)
            return ShortcutMixin._shortcut_dialog_open(host), (str(target) if target is not None else None)

        def old(self):
            root.update()
            return former.dialog_open(), former.escape_target()

        def check(self):
            new = self.new()
            assert new == self.old()
            assert unregistered_visible_toplevels(root) == []
            return new

    yield Scene()
    for item in reversed(opened):
        try:
            if isinstance(item, tuple):
                bar, anchor, suspended = item
                bar.close_popups_from_level(0)
                suspended.__exit__(None, None, None)
                anchor.destroy()
            else:
                item.destroy()
        except tkinter.TclError:
            pass
    root.update()


def test_nothing_open(scene):
    assert scene.check() == (False, None)


def test_tracked_and_scanned_modal_windows_block(scene):
    dialog = scene.modal()
    assert scene.check() == (True, str(dialog))
    scanned = scene.modal(tracked=False)  # nur vom Scan erfasst, ebenfalls Dialog
    assert scene.check() == (True, str(scanned))


def test_seating_preview_no_longer_blocks(scene):
    """Bewusste Änderung: früher sperrte die (nicht getrackte) Vorschau als Dialog, jetzt Werkzeugfenster."""
    preview = ui.Toplevel(scene_root := scene.root_widget())
    PopupMixin._register_popup_window(SimpleNamespace(tk_root=scene_root), preview, blocking_shortcuts=False)
    scene.keep(preview)
    old_open, _old_target = scene.old()
    assert old_open is True
    assert scene.new() == (False, str(preview))


def test_tool_windows_do_not_block(scene):
    tool = scene.tool_window()
    assert scene.check() == (False, str(tool))


def test_menu_popup_is_an_escape_target_but_does_not_block(scene):
    popup = scene.menu()
    assert scene.check() == (False, str(popup))


def test_nested_modal_dialog_is_the_documented_unobservable_difference(scene):
    """Snapshot-Löschen hängt im Snapshot-Fenster: früher nicht gezählt, jetzt modal (grab_set)."""
    snapshots = scene.tool_window()
    nested = scene.modal(tracked=False, parent=snapshots)
    assert scene.old() == (False, str(snapshots))
    assert scene.new() == (True, str(nested))


def test_combinations_and_closing(scene):
    tool = scene.tool_window()
    dialog = scene.modal()
    popup = scene.menu()
    assert scene.check() == (True, str(popup))
    dialog.destroy()
    assert scene.check() == (False, str(popup))
    assert tool.winfo_exists()
