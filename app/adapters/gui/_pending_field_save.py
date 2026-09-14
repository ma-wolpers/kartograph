"""Entitätsgebundener Pending-Save-Baustein für Detail-Panel-Felder.

Wird für Namensfelder und das Nachteilsausgleiche-Feld verwendet (s.
``_mixin_details.py``), um zu verhindern, dass ein Tischwechsel eine noch
nicht gespeicherte Eingabe verwirft (historischer Bug: das Nachteils-
ausgleiche-Feld verließ sich ausschließlich auf ``<FocusOut>``, das beim
Tischwechsel strukturell zu spät kommt, weil das Detail-Panel schon vorher
für den neuen Schüler neu gerendert wird).
"""

from __future__ import annotations

from typing import Any, Callable

from app.adapters.gui.main_window_constants import DEFAULT_SAVE_DELAY
from app.core.domain.student_id import StudentId


class PendingFieldSave:
    """Entitätsgebundener (StudentId) Pending Save mit Debounce UND
    expliziter Commit-Semantik bei Entity-/Kontextwechseln.

    Drei Flush-Wege, alle idempotent und gleichwertig:
    (1) der Debounce-Timer läuft ab,
    (2) eine Änderung für eine ANDERE StudentId wird beobachtet -- das
        bisherige Pending wird zuerst geflusht,
    (3) ein expliziter Kontextwechsel ruft ``flush()`` auf (i. d. R. über
        ``_commit_pending_edits()``), bevor der Bearbeitungskontext wechselt.

    Nicht an ein Widget oder dessen Anzeigezustand gebunden -- ein
    Kontextwechsel (anderer Tisch, Panel geschlossen, Widget programmatisch
    neu befüllt) darf einen noch nicht gespeicherten Wert niemals verwerfen.
    """

    def __init__(
        self,
        window,
        *,
        capture: Callable[[], tuple[StudentId, Any] | None],
        apply: Callable[[StudentId, Any], None],
    ) -> None:
        self._window = window
        self._capture = capture
        self._apply = apply
        self._pending: tuple[StudentId, Any] | None = None
        self._after_id: str | None = None

    def note_change(self) -> None:
        """Erfasst den aktuellen Feldwert sofort unter der zugehörigen StudentId.

        Gehört ein bereits ausstehender Wert zu einer ANDEREN StudentId, wird
        er zuerst geflusht, bevor der neue Wert übernommen wird.
        """
        captured = self._capture()
        if captured is None:
            return
        student_id, value = captured
        if self._pending is not None and self._pending[0] != student_id:
            self.flush()
        self._pending = (student_id, value)
        self._reschedule()

    def flush(self) -> None:
        """Speichert einen ausstehenden Wert sofort, falls vorhanden (sonst No-Op)."""
        if self._after_id is not None:
            try:
                self._window.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        pending, self._pending = self._pending, None
        if pending is not None:
            self._apply(*pending)

    def _reschedule(self) -> None:
        if self._after_id is not None:
            try:
                self._window.after_cancel(self._after_id)
            except Exception:
                pass
        delay_ms = int(getattr(self._window, "save_delay", DEFAULT_SAVE_DELAY) * 1000)
        if delay_ms <= 0:
            self.flush()
            return
        self._after_id = self._window.after(delay_ms, self.flush)
