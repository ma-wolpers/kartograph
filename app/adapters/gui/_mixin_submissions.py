"""Mixin "Abgaben zählen" (Extras-Menü): ZIP prüfen, Fehlende markieren, im Mappenblick bewerten.

Ablauf: Datumsspalte aktiv → ZIP wählen → Ordner mit dem Plan abgleichen →
bei vorhandenen Einträgen fragen (ersetzen/ergänzen) → Startdialog
(Zusammenfassung, Zuordnung offener Ordner, Abwesende-Checkbox) → X für
Fehlende (ein Undo-Schritt) → nicht-modaler Viewer, der jede Bewertung
sofort als eigenen Undo-Schritt einträgt. Alles Mappenblick-Spezifische
liegt in ``_mappenblick_viewer.py``; dieses Mixin kennt nur dessen API.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

from app.adapters.gui._mappenblick_viewer import SubmissionArchive, open_viewer_window
from app.adapters.gui.dialog_services import filedialog, messagebox
from app.core.domain.models_v4 import Student
from app.core.domain.student_id import StudentId
from app.core.domain.submission_matching import MatchResult, match_submission_folders
from app.core.domain.submission_status import (
    ABSENT_CODEPOINT,
    CatalogSymbolMissing,
    SubmissionStatus,
    resolve_symbol_name,
    submission_symbol_names,
)
from app.core.intents.submission_intents import ApplyMissingSubmissionsIntent, SetSubmissionStatusIntent
from app.core.intents.view_intents import UpdateSettingsIntent
from app.core.usecases.v4.submission_usecases import rated_statuses
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.menu import MenuItem as SharedMenuItem
from bw_gui.runtime import on_combobox_select, ui
from bw_gui.runtime import widgets as tui
from bw_gui.widgets import Checkbox

_IGNORE = "– ignorieren –"
_ZIP_FILETYPES = [("Zip-Archive", "*.zip"), ("Alle Dateien", "*.*")]


class SubmissionsMixin:
    """Mixin: Extras → "Abgaben zählen…" inklusive Startdialog und Bewertungs-Viewer."""

    _submission_viewer: ui.Toplevel | None = None
    _submission_viewer_plan_path: Path | None = None

    def _menu_items_extras(self):
        """Liefert das Extras-Menü; "Abgaben zählen…" nur mit aktiver Datumsspalte in der Doku-Ansicht."""
        date = self._submission_target_date()
        if date is None:
            return (SharedMenuItem(type="disabled", label="Abgaben zählen… (in der Doku-Ansicht ein Datum wählen)"),)
        return (SharedMenuItem(type="command", label=f"Abgaben zählen… ({date})", command=self.count_submissions_dialog),)

    def _submission_target_date(self) -> str | None:
        """Gibt das aktive Doku-Datum zurück, wenn eine Datumsspalte (nicht Name/Note) aktiv ist."""
        if not self.current_plan or self._editor_surface != "docs" or not self._doc_dates:
            return None
        if self._doc_selected_nondate_column_id is not None:
            return None
        return self._doc_anchor_date()

    def count_submissions_dialog(self) -> None:
        """Startet "Abgaben zählen" für das aktive Datum (Dateidialog, Abgleich, Rückfrage, Startdialog).

        Fehler beim Öffnen der ZIP oder fehlende Katalogsymbole werden als
        Meldung gezeigt; am Plan ändert sich bis zum "Starten" nichts.
        """
        date = self._submission_target_date()
        if date is None:
            return
        selected = filedialog.askopenfilename(parent=self, title="Abgaben-ZIP wählen", filetypes=_ZIP_FILETYPES)
        if not selected:
            return
        try:
            archive = SubmissionArchive(Path(selected))
            names = submission_symbol_names(self._controller.state.symbol_catalog)
        except CatalogSymbolMissing as err:
            messagebox.showerror("Abgaben zählen", str(err), parent=self)
            return
        except Exception as err:
            messagebox.showerror("ZIP konnte nicht geöffnet werden", str(err), parent=self)
            return
        existing = rated_statuses(self.current_plan, date, names)
        mode = "replace"
        if existing:
            answer = messagebox.askyesnocancel(
                "Abgaben zählen",
                f"Für {date} gibt es schon {len(existing)} Abgabe-Einträge (✓/◐/X).\n\n"
                "Ja: alle ersetzen\nNein: nur Fehlendes ergänzen (bereits Bewertete bleiben)",
                parent=self,
            )
            if answer is None:
                return
            mode = "replace" if answer else "complement"
        match = match_submission_folders(archive.folder_names, self.current_plan.classroom.students)
        self._open_submission_start_dialog(archive, date, match, existing, mode)

    def _open_submission_start_dialog(
        self,
        archive: SubmissionArchive,
        date: str,
        match: MatchResult,
        existing: dict[StudentId, SubmissionStatus],
        mode: str,
    ) -> None:
        """Zeigt Zusammenfassung, Zuordnung offener Ordner und die Abwesende-Checkbox.

        Die Zusammenfassung rechnet bei jeder Zuordnung live neu, damit die
        Zahlen vor dem Start stimmen.

        Args:
            archive: Geöffnete ZIP.
            date: Doku-Tag.
            match: Automatischer Abgleich.
            existing: Bereits eingetragene Status des Tages.
            mode: ``"replace"`` oder ``"complement"``.
        """
        students = {s.student_id: s for s in self.current_plan.classroom.students if s.is_named()}
        sid_by_label = _unique_labels(students)
        absent_ids = self._absent_student_ids(date)
        dialog = self._create_overlay_dialog(f"Abgaben zählen – {date}", "620x560")
        container = tui.Frame(dialog)
        container.pack(fill="both", expand=True, padx=12, pady=12)
        summary_var = ui.StringVar()
        tui.Label(container, textvariable=summary_var, justify="left").pack(anchor="w", pady=(0, 10))
        choice_vars: dict[str, ui.StringVar] = {}
        open_folders = [*match.ambiguous, *match.unknown]
        if open_folders:
            tui.Label(container, text="Nicht eindeutig zugeordnete Ordner:").pack(anchor="w", pady=(0, 4))
        for folder in open_folders:
            row = tui.Frame(container)
            row.pack(fill="x", pady=2)
            tui.Label(row, text=folder, width=32, anchor="w").pack(side="left")
            choice_vars[folder] = ui.StringVar(value=_IGNORE)
            box = tui.Combobox(row, textvariable=choice_vars[folder], state="readonly", values=[_IGNORE, *sid_by_label])
            box.pack(side="left", fill="x", expand=True)
            on_combobox_select(box, lambda _change: update_summary())
        absent_var = ui.BooleanVar(value=self._controller.state.settings.submission_mark_absent)
        Checkbox(container, text="Abwesende ohne Abgabe ebenfalls mit X markieren", variable=absent_var,
                 on_select=lambda _value: update_summary()).pack(anchor="w", pady=(10, 10))

        def assignments() -> dict[str, StudentId]:
            chosen = {f: sid_by_label[v.get()] for f, v in choice_vars.items() if v.get() != _IGNORE}
            return {**match.matched, **chosen}

        def update_summary() -> None:
            submitted = set(assignments().values())
            missing = [sid for sid in students if sid not in submitted]
            absent = [sid for sid in missing if sid in absent_ids]
            marked = len(missing) if absent_var.get() else len(missing) - len(absent)
            unassigned = sum(1 for v in choice_vars.values() if v.get() == _IGNORE)
            summary_var.set(
                f"Abgegeben: {len(submitted)} von {len(students)}\n"
                f"Ohne Abgabe: {len(missing)} (davon abwesend: {len(absent)}) → {marked}× X\n"
                f"Nicht zugeordnete Ordner: {unassigned}"
                + ("\nModus: nur Fehlendes ergänzen" if mode == "complement" else "")
            )

        def start() -> None:
            assigned = assignments()
            if len(set(assigned.values())) != len(assigned):
                messagebox.showerror("Abgaben zählen", "Eine Person ist mehreren Ordnern zugeordnet.", parent=dialog)
                return
            self._destroy_tracked_dialog(dialog)
            self._start_submission_run(archive, date, assigned, existing, mode, absent_var.get(), students)

        update_summary()
        buttons = tui.Frame(container)
        buttons.pack(fill="x", side="bottom")
        tui.Button(buttons, text="Starten", command=start).pack(side="right")
        tui.Button(buttons, text="Abbrechen", command=lambda: self._destroy_tracked_dialog(dialog)).pack(side="right", padx=(0, 6))

    def _start_submission_run(
        self,
        archive: SubmissionArchive,
        date: str,
        assigned: dict[str, StudentId],
        existing: dict[StudentId, SubmissionStatus],
        mode: str,
        mark_absent: bool,
        students: dict[StudentId, Student],
    ) -> None:
        """Merkt die Checkbox, setzt X für Fehlende und öffnet den Bewertungs-Viewer.

        Args:
            archive: Geöffnete ZIP.
            date: Doku-Tag.
            assigned: Ordner → Person (eindeutig).
            existing: Vor dem Lauf eingetragene Status.
            mode: ``"replace"`` oder ``"complement"``.
            mark_absent: Wert der Abwesende-Checkbox.
            students: Benannte Personen nach ID.
        """
        settings = self._controller.state.settings
        if settings.submission_mark_absent != mark_absent:
            self._controller.dispatch(UpdateSettingsIntent(settings=dataclasses.replace(settings, submission_mark_absent=mark_absent)))
        self._controller.dispatch(
            ApplyMissingSubmissionsIntent(date=date, submitted=tuple(assigned.values()), mark_absent=mark_absent, mode=mode)
        )
        plan_path = self.current_plan_path
        keep_existing = mode == "complement"

        def on_rated(folder: str, status: SubmissionStatus) -> None:
            if self.current_plan_path == plan_path and folder in assigned:
                self._controller.dispatch(SetSubmissionStatusIntent(student_id=assigned[folder], date=date, status=status))

        self._close_submission_viewer()
        self._submission_viewer = open_viewer_window(
            self,
            archive,
            title=f"Abgaben {date} – {self.current_plan.meta.name}",
            folders=[f for f, sid in assigned.items() if not (keep_existing and sid in existing)],
            labels={f: students[sid].display_name() for f, sid in assigned.items()},
            initial={f: existing[sid] for f, sid in assigned.items() if keep_existing and sid in existing},
            on_rated=on_rated,
            register_window=lambda window: self._register_popup_window(window, blocking_shortcuts=False),
        )
        self._submission_viewer_plan_path = plan_path

    def _absent_student_ids(self, date: str) -> set[StudentId]:
        """Gibt die Personen zurück, die an *date* als abwesend (∅) markiert sind."""
        try:
            absent = resolve_symbol_name(self._controller.state.symbol_catalog, ABSENT_CODEPOINT)
        except CatalogSymbolMissing:
            return set()
        session = self.current_plan.documentation.session_for_date(date)
        if session is None:
            return set()
        return {sid for sid, entry in session.entries.items() if entry.symbols.get(absent)}

    def _close_submission_viewer(self) -> None:
        """Schließt einen offenen Bewertungs-Viewer (falls vorhanden)."""
        viewer = self._submission_viewer
        self._submission_viewer = None
        self._submission_viewer_plan_path = None
        if viewer is not None and int(viewer.winfo_exists()):
            viewer.destroy()

    def _close_submission_viewer_if_plan_changed(self) -> None:
        """Schließt den Viewer, wenn ein anderer (oder kein) Plan geöffnet wurde; aus ``apply_state``."""
        if self._submission_viewer is not None and self.current_plan_path != self._submission_viewer_plan_path:
            self._close_submission_viewer()


def _unique_labels(students: dict[StudentId, Student]) -> dict[str, StudentId]:
    """Ordnet jeder Person einen eindeutigen Anzeigenamen zu, alphabetisch sortiert.

    Gleichnamige Personen bekommen *alle* ihren Sitzplatz angehängt, damit
    keine von ihnen nur "der Name ohne Zusatz" ist.

    Args:
        students: Benannte Personen nach ID.
    """
    counts = Counter(student.display_name() for student in students.values())
    by_label: dict[str, StudentId] = {}
    for sid, student in sorted(students.items(), key=lambda item: item[1].display_name().casefold()):
        label = student.display_name()
        if counts[label] > 1:
            label = f"{label} ({student.seat.x},{student.seat.y})"
        by_label[label] = sid
    return by_label
