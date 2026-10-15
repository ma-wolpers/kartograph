"""Dialog- und widgetlokale Tastenkürzel über die bw-gui-Binder.

Kartograph bindet Tasten nie mehr per ``widget.bind("<Return>", ...)``: Dialoge
bekommen einen ``WindowShortcutBinder`` (Bindtag = Toplevel-Pfad, gehört bw-gui),
einzelne Widgets (Namensfelder, Inline-Editor, Listen, Toolbar-Buttons) einen
``WidgetShortcutBinder`` (Bindtag direkt hinter dem Widget, vor den nativen
Klassenbindings). Beide werden pro Fenster bzw. Widget genau einmal angelegt und
am Tk-Objekt zwischengespeichert; sie leben bis zu dessen ``<Destroy>``.

Aktionen sind parameterlose Callables; eine ausgeführte Aktion beendet die
Verarbeitung des Tastenereignisses (``HANDLED``), wie früher ``return "break"``
bzw. wie das Schließen des Dialogs, nach dem nichts mehr zu tun war.

Toleranzen: ``Enter``/``Escape`` tolerieren Shift (früher feuerte ``<Return>``
nach Tks Mindestmengen-Semantik auch mit Shift). ``Enter`` umfasst ``KP_Enter``.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult, KeySpec
from bw_gui.runtime import WidgetShortcutBinder, WindowShortcutBinder

ENTER = KeySpec.parse("Enter (tolerate: Shift)")
ESCAPE = KeySpec.parse("Escape (tolerate: Shift)")

_ATTRIBUTE = "_kartograph_local_keys"


def dialog_keys(dialog: Any) -> WindowShortcutBinder:
    """Liefert den (einzigen) Fenster-Binder des Dialog-Toplevels *dialog*.

    Gating: Standard-Text-Input-Contract von bw-gui, kein Modus, kein Dialog-Gating
    (der Dialog ist selbst das oberste Fenster).

    Args:
        dialog: Toplevel des Dialogs.

    Returns:
        Der am Toplevel zwischengespeicherte ``WindowShortcutBinder``.
    """
    binder = getattr(dialog, _ATTRIBUTE, None)
    if binder is None:
        binder = WindowShortcutBinder(dialog)
        setattr(dialog, _ATTRIBUTE, binder)
    return binder


def widget_keys(widget: Any) -> WidgetShortcutBinder:
    """Liefert den (einzigen) Widget-Binder von *widget*.

    Args:
        widget: Das Widget, dessen Tastenereignisse gebunden werden.

    Returns:
        Der am Widget zwischengespeicherte ``WidgetShortcutBinder``.
    """
    binder = getattr(widget, _ATTRIBUTE, None)
    if binder is None:
        binder = WidgetShortcutBinder(widget)
        setattr(widget, _ATTRIBUTE, binder)
    return binder


def bind_action(
    binder: Any,
    keys: KeySpec | Iterable[KeySpec],
    action: Callable[[], object],
    *,
    binding_id: str,
    text: bool = True,
) -> None:
    """Bindet *keys* an die parameterlose *action* (Ergebnis: ``HANDLED``).

    Args:
        binder: ``dialog_keys(...)`` oder ``widget_keys(...)``.
        keys: Eine ``KeySpec`` oder alternative Specs derselben Aktion.
        action: Auszuführende Aktion; ihr Rückgabewert wird ignoriert.
        binding_id: Eindeutige ID innerhalb des Binders (dient auch als Intent).
        text: Auch bei fokussiertem Texteingabe-Widget aktiv (Default ``True``:
            Return/Escape in Eingabefeldern von Dialogen lösen wie bisher aus).
    """

    def _run(_event) -> EventResult:
        action()
        return EventResult.HANDLED

    binder.bind(keys, _run, binding_id=binding_id, intent=binding_id, allow_when_text_input=text)
