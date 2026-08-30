"""Debounced-Speichern-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Verzögert den eigentlichen Festplatten-Schreibvorgang nach einem Symbol-/
Noten-/Farb-Edit (statt ihn synchron bei jedem einzelnen Edit auszuführen),
damit eine schnelle Serie solcher Edits (z. B. eine ganze Notenspalte
durchgehen) nur einen Schreibvorgang statt vieler auslöst. Der Undo/Redo-
Verlauf (``PlanHistory.record()``) bleibt davon unberührt — der bleibt
synchron, nur das eigentliche ``save_plan()`` wird verzögert (siehe
``HandlerContext.plan_save_scheduler`` und ``_shared.py::_record_and_save``).

Nutzt dieselbe Einstellung wie der bestehende Namens-Debounce
(``self.save_delay``, vormals ``name_save_delay`` — auf Nutzerwunsch
zusammengelegt, damit es nicht zwei unabhängige "wie lange warten bis
Speichern"-Werte gibt) und exakt dasselbe Muster
(``_mixin_details.py::_schedule_name_save``/``_flush_pending_name_save``):
ein einzelner ausstehender Save-Slot, `after()`/`after_cancel()` für die
Verzögerung, und ein `flush()`, der an denselben Stellen aufgerufen wird wie
der Namens-Flush (Fensterschließen, Planwechsel, Verlassen des Editors).
``MIN_SAVE_DELAY`` (0.3s) ist hart erzwungen; darüber ist der Wert frei
einstellbar, mit einer im Einstellungsdialog nur empfohlenen (nicht
erzwungenen) Obergrenze von ``RECOMMENDED_MAX_SAVE_DELAY`` (10s) — länger
bedeutet ein größeres Zeitfenster, in dem bei einem harten Absturz mehr
Edits noch nicht auf der Festplatte wären.

Bewusst kein neues Konflikt-Auflösungssystem: ``JsonSeatingPlanRepositoryV4.
save_plan()`` überschreibt die Zieldatei unconditional (atomarer Schreibvor-
gang schützt nur vor Korruption durch einen abgebrochenen Schreibvorgang,
nicht vor einer parallelen externen Änderung derselben Datei — "letzter
Schreiber gewinnt" gilt bereits ohne dieses Debouncing). Das Debouncing
vergrößert das Zeitfenster für eine solche externe Kollision nur um die
konfigurierte Verzögerung, nicht grundsätzlich — dieselbe Race-Bedingung
bestand vorher bei jedem synchronen Save ebenfalls, nur mit einem kürzeren
(oder gar keinem) Fenster.
"""

from __future__ import annotations

from pathlib import Path

from app.adapters.gui.main_window_constants import DEFAULT_SAVE_DELAY, LOGGER
from app.core.domain.models_v4 import SeatingPlan


class PlanSaveMixin:
    """Mixin: debounced Speichern von Sitzplan-Edits auf die Festplatte (v4)."""

    def _schedule_plan_save(self, plan: SeatingPlan, path: Path) -> None:
        """Plant einen verzögerten Schreibvorgang; ersetzt einen bereits ausstehenden.

        Wird als ``ctx.plan_save_scheduler`` an den Controller gebunden
        (s. ``main_window.py``) und von ``_record_and_save()`` statt eines
        direkten ``plan_repository.save_plan()``-Aufrufs verwendet. Nur der
        jeweils *letzte* geplante Zustand wird am Ende tatsächlich
        geschrieben — dazwischenliegende Zwischenstände sind im
        Undo-Verlauf bereits erfasst (``ctx.history.record()`` bleibt
        synchron) und müssen nicht einzeln auf die Festplatte.

        Args:
            plan: Zu speichernder Planzustand (bereits vollständig; keine
                weitere Kopie nötig, da Usecases nach dem Immutable-Update-
                Muster arbeiten und dieses Objekt von späteren Edits nicht
                mehr mutiert wird).
            path: Zieldatei für den Schreibvorgang.
        """
        if self._plan_save_after_id is not None:
            try:
                self.after_cancel(self._plan_save_after_id)
            except Exception:
                pass
            self._plan_save_after_id = None

        self._pending_plan_save = (plan, path)
        delay_ms = int(getattr(self, "save_delay", DEFAULT_SAVE_DELAY) * 1000)
        if delay_ms <= 0:
            self._flush_pending_plan_save()
            return
        self._plan_save_after_id = self.after(delay_ms, self._flush_pending_plan_save)

    def _flush_pending_plan_save(self) -> None:
        """Schreibt einen ausstehenden Speichervorgang sofort, falls vorhanden.

        Wird vom Debounce-Timer selbst sowie von allen Stellen aufgerufen, an
        denen auch der Namens-Flush (``_flush_pending_name_save``) ausgelöst
        wird (Fensterschließen, Planwechsel/-neuanlage, Verlassen des
        Editors) — dieselben Momente, in denen ein ausstehender Schreib-
        vorgang nicht verloren gehen darf. Fehler werden geloggt und über die
        Statuszeile sichtbar gemacht, statt in einem Tk-``after()``-Callback
        still zu verschwinden.
        """
        if self._plan_save_after_id is not None:
            try:
                self.after_cancel(self._plan_save_after_id)
            except Exception:
                pass
            self._plan_save_after_id = None

        pending = self._pending_plan_save
        self._pending_plan_save = None
        if pending is None:
            return

        plan, path = pending
        try:
            self._controller.plan_repository.save_plan(plan, path)
        except Exception as exc:
            LOGGER.exception("Verzögertes Speichern von %s fehlgeschlagen", path)
            self.status_var.set(f"Speichern fehlgeschlagen: {exc}")
