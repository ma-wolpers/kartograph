"""Entitätsgebundener Pending-Save-Baustein für Detail-Panel-Felder.

Wird für Namensfelder und das Notizfeld verwendet (s.
``_mixin_details.py``), um zu verhindern, dass ein Tischwechsel eine noch
nicht gespeicherte Eingabe verwirft (historischer Bug: das Nachteils-
ausgleiche-Feld verließ sich ausschließlich auf ``<FocusOut>``, das beim
Tischwechsel strukturell zu spät kommt, weil das Detail-Panel schon vorher
für den neuen Schüler neu gerendert wird).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Callable

from app.core.domain.settings import DEFAULT_SAVE_DELAY
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
        apply: Callable[[StudentId, Any], None],
        capture: Callable[[], tuple[StudentId, Any] | None] | None = None,
        delay_seconds: Callable[[], float] | None = None,
    ) -> None:
        """Legt einen leeren Pending-Slot an.

        Args:
            window: Tk-Fenster für ``after``/``after_cancel``.
            apply: Speichert einen Wert ``(student_id, value)``.
            capture: Liest das Feld für ``note_change``; ohne *capture* nur ``put``.
            delay_seconds: Frist bis zum Speichern; Standard ist ``window.save_delay``.
        """
        self._window = window
        self._capture = capture
        self._apply = apply
        self._delay_seconds = delay_seconds or (lambda: getattr(window, "save_delay", DEFAULT_SAVE_DELAY))
        self._pending: tuple[StudentId, Any] | None = None
        self._after_id: str | None = None
        self._suspend_depth = 0

    @contextmanager
    def suspended(self) -> Iterator[None]:
        """Programmatisches Befüllen der Felder zählt in diesem Block nicht als Eingabe.

        Das Details-Panel lädt die gespeicherten Werte über diesen Block in die
        Felder (``StringVar``-Traces feuern auch dabei). Ohne ihn entstünde ein
        "ausstehender" Wert, der nur den geladenen Stand wiederholt -- ein Undo
        kurz danach würde dann von diesem Scheinwert überschrieben. Verschachtelbar.
        """
        self._suspend_depth += 1
        try:
            yield
        finally:
            self._suspend_depth -= 1

    def has_pending_for(self, student_id: StudentId) -> bool:
        """Gibt an, ob für *student_id* eine noch nicht gespeicherte Eingabe wartet.

        Args:
            student_id: Die angezeigte Person.

        Returns:
            ``True``, solange ein Wert dieser Person auf das Speichern wartet.
        """
        return self._pending is not None and self._pending[0] == student_id

    def note_change(self) -> None:
        """Erfasst den aktuellen Feldwert sofort unter der zugehörigen StudentId.

        Gehört ein bereits ausstehender Wert zu einer ANDEREN StudentId, wird
        er zuerst geflusht, bevor der neue Wert übernommen wird. Innerhalb von
        ``suspended()`` (programmatisches Befüllen) ein No-Op.
        """
        if self._suspend_depth or self._capture is None:
            return
        captured = self._capture()
        if captured is not None:
            self.put(*captured)

    def put(self, student_id: StudentId, value: Any) -> None:
        """Merkt *value* für *student_id* vor und startet die Frist neu.

        Wartet schon ein Wert einer ANDEREN Person, wird er zuerst gespeichert.

        Args:
            student_id: Betroffene Person.
            value: Zu speichernder Wert.
        """
        if self._pending is not None and self._pending[0] != student_id:
            self.flush()
        self._pending = (student_id, value)
        self._reschedule()

    def pending_value(self, student_id: StudentId) -> Any | None:
        """Der wartende Wert von *student_id* oder ``None``.

        Args:
            student_id: Die angezeigte Person.
        """
        return self._pending[1] if self.has_pending_for(student_id) else None

    def discard(self, student_id: StudentId) -> None:
        """Verwirft den wartenden Wert von *student_id* ohne zu speichern (sonst No-Op).

        Args:
            student_id: Person, deren Vormerkung entfällt.
        """
        if self.has_pending_for(student_id):
            self._cancel_timer()
            self._pending = None

    def flush(self) -> None:
        """Speichert einen ausstehenden Wert sofort, falls vorhanden (sonst No-Op)."""
        self._cancel_timer()
        pending, self._pending = self._pending, None
        if pending is not None:
            self._apply(*pending)

    def cancel(self) -> None:
        """Verwirft den geplanten Rückruf ohne zu speichern (nur beim Zerstören des Fensters).

        Der reguläre Schließweg hat ausstehende Werte vorher per ``flush``
        gespeichert (``_on_shell_close`` → ``_commit_pending_edits``); hier geht
        es nur darum, dass kein ``after``-Rückruf das Fenster überlebt.
        """
        self._cancel_timer()

    def _cancel_timer(self) -> None:
        """Bricht den geplanten Speicher-Rückruf ab, falls einer läuft."""
        if self._after_id is not None:
            try:
                self._window.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _reschedule(self) -> None:
        """Startet die Frist (``delay_seconds``) neu; ``0`` speichert sofort."""
        self._cancel_timer()
        delay_ms = int(self._delay_seconds() * 1000)
        if delay_ms <= 0:
            self.flush()
            return
        self._after_id = self._window.after(delay_ms, self.flush)
