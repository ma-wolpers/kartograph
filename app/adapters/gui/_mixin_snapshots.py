"""Snapshots-Verwaltung-Popup-Mixin für das Kartograph-Hauptfenster.

Listenansicht aller gespeicherten Snapshots (benannte Momentaufnahmen der
Tischkoordinaten, ohne Diagnose-/Dokumentationsdaten) mit Erstellen/Laden/
Umbenennen/Löschen. "Aktuell geladen" und "positionsgleich" sind keine
gespeicherten Felder, sondern werden bei jedem Öffnen/Refresh live gegen den
aktuellen Plan berechnet (``app.core.domain.snapshot_matching``) -- mehrere
Snapshots können daher gleichzeitig als "aktuell geladen" erscheinen.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from app.adapters.gui.dialog_services import messagebox, simpledialog
from app.core.domain.snapshot_matching import is_full_match, positions_match
from app.core.intents.snapshot_intents import (
    CreateSnapshotIntent,
    DeleteSnapshotIntent,
    RenameSnapshotIntent,
    RestoreSnapshotIntent,
)
from app.core.intents.view_intents import UpdateSettingsIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui
from bw_gui.widgets import Checkbox


def _format_timestamp(raw: str) -> str:
    """Wandelt eine ISO-8601-Zeitangabe in eine lesbare Anzeige um.

    Gibt den rohen Text unverändert zurück, wenn er sich nicht parsen lässt
    (z. B. leer bei einer per Hand bearbeiteten Plandatei).

    Args:
        raw: ISO-8601-Datetime-String (``created_at``/``last_used_at``).
    """
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return raw


class SnapshotsMixin:
    """Mixin: Snapshots-Verwaltung-Popup (Erstellen/Laden/Umbenennen/Löschen)."""

    def open_snapshots_popup(self) -> None:
        """Öffnet das Snapshots-Popup oder bringt es in den Vordergrund."""
        if self._snapshot_window is not None and int(self._snapshot_window.winfo_exists()):
            self._refresh_snapshot_table()
            self._snapshot_window.deiconify()
            self._snapshot_window.lift()
            self._snapshot_window.focus_force()
            return

        window = ui.Toplevel(self)
        window.title("Snapshots")
        window.geometry("640x420")
        window.minsize(480, 320)
        self._track_popup_window(window, policy_id="dialog.non_blocking")

        toolbar = tui.Frame(window, padding=(10, 8))
        toolbar.pack(fill="x")
        self._snapshot_add_button = tui.Button(
            toolbar, text="Aktuellen Sitzplan speichern…", command=self._add_current_as_snapshot
        )
        self._snapshot_add_button.pack(side="left")
        self._attach_hover_help(
            self._snapshot_add_button,
            label="Aktuelle Tischkoordinaten als neuen Snapshot speichern",
            shortcut=None,
        )
        self._snapshot_load_button = tui.Button(
            toolbar, text="Laden", command=self._load_selected_snapshot, state="disabled"
        )
        self._snapshot_load_button.pack(side="left", padx=(8, 0))
        self._snapshot_rename_button = tui.Button(
            toolbar, text="Umbenennen", command=self._rename_selected_snapshot, state="disabled"
        )
        self._snapshot_rename_button.pack(side="left", padx=(8, 0))
        self._snapshot_delete_button = tui.Button(
            toolbar, text="Löschen", command=self._delete_selected_snapshot, state="disabled"
        )
        self._snapshot_delete_button.pack(side="left", padx=(8, 0))

        body = tui.Frame(window, padding=(10, 0, 10, 8))
        body.pack(fill="both", expand=True)
        columns = ("name", "created", "last_used", "status")
        table = tui.Treeview(body, columns=columns, show="headings")
        table.heading("name", text="Name")
        table.heading("created", text="Erstellt")
        table.heading("last_used", text="Zuletzt verwendet")
        table.heading("status", text="Status")
        table.column("name", width=180, anchor="w", stretch=True)
        table.column("created", width=130, anchor="center", stretch=False)
        table.column("last_used", width=130, anchor="center", stretch=False)
        table.column("status", width=190, anchor="w", stretch=False)
        table.pack(side="left", fill="both", expand=True)
        y_scroll = tui.Scrollbar(body, orient="vertical", command=table.yview)
        y_scroll.pack(side="right", fill="y")
        table.configure(yscrollcommand=y_scroll.set)
        table.bind("<<TreeviewSelect>>", lambda _e: self._on_snapshot_selection_changed())
        table.bind("<Double-Button-1>", lambda _e: self._load_selected_snapshot())

        self._snapshot_window = window
        self._snapshot_table = table
        window.protocol("WM_DELETE_WINDOW", self._close_snapshots_popup)
        self._refresh_snapshot_table()

    def _close_snapshots_popup(self) -> None:
        """Schließt das Snapshots-Popup und meldet es aus der Popup-Registry ab."""
        if self._snapshot_window is not None and int(self._snapshot_window.winfo_exists()):
            popup_id = str(self._snapshot_window)
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)
            self._snapshot_window.destroy()
        self._snapshot_window = None
        self._snapshot_table = None
        self._snapshot_add_button = None
        self._snapshot_load_button = None
        self._snapshot_rename_button = None
        self._snapshot_delete_button = None

    def _refresh_snapshot_table(self) -> None:
        """Baut die Snapshot-Tabelle neu auf, sortiert nach ``last_used_at`` absteigend.

        Berechnet "aktuell geladen"/"positionsgleich" live gegen ``self.current_plan``
        (keine gespeicherten Felder) und (de)aktiviert den "Speichern"-Button, wenn
        der aktuelle Zustand bereits vollständig als Snapshot existiert
        (Duplikat-Sperre aus der Produktentscheidung).
        """
        table = self._snapshot_table
        if table is None:
            return
        table.delete(*table.get_children())
        plan = self.current_plan

        if self._snapshot_add_button is not None:
            blocked = plan is None or any(is_full_match(s, plan) for s in plan.snapshots)
            self._snapshot_add_button.configure(state="disabled" if blocked else "normal")

        if plan is None:
            self._on_snapshot_selection_changed()
            return

        for snapshot in sorted(plan.snapshots, key=lambda s: s.last_used_at, reverse=True):
            if is_full_match(snapshot, plan):
                status = "✓ aktuell geladen"
            elif positions_match(snapshot, plan):
                status = "≈ positionsgleich (andere Klassenliste)"
            else:
                status = ""
            table.insert(
                "", ui.END,
                iid=snapshot.snapshot_id,
                values=(
                    snapshot.name,
                    _format_timestamp(snapshot.created_at),
                    _format_timestamp(snapshot.last_used_at),
                    status,
                ),
            )
        self._on_snapshot_selection_changed()

    def _selected_snapshot_id(self) -> str | None:
        """Gibt die ID des in der Tabelle ausgewählten Snapshots zurück, oder ``None``."""
        table = self._snapshot_table
        if table is None:
            return None
        selected = table.selection()
        return selected[0] if selected else None

    def _on_snapshot_selection_changed(self) -> None:
        """(De)aktiviert Laden-/Umbenennen-/Löschen-Buttons je nach Auswahl.

        "Laden" bleibt deaktiviert, wenn der ausgewählte Snapshot den aktuellen
        Zustand bereits vollständig beschreibt (No-Op-Fall aus der
        Produktentscheidung -- ein Klick würde ohnehin nichts ändern).
        """
        snapshot_id = self._selected_snapshot_id()
        has_selection = snapshot_id is not None
        already_loaded = False
        if has_selection and self.current_plan is not None:
            snapshot = self.current_plan.snapshot_by_id(snapshot_id)
            already_loaded = snapshot is not None and is_full_match(snapshot, self.current_plan)
        if self._snapshot_load_button is not None:
            self._snapshot_load_button.configure(state="normal" if has_selection and not already_loaded else "disabled")
        if self._snapshot_rename_button is not None:
            self._snapshot_rename_button.configure(state="normal" if has_selection else "disabled")
        if self._snapshot_delete_button is not None:
            self._snapshot_delete_button.configure(state="normal" if has_selection else "disabled")

    def _add_current_as_snapshot(self) -> None:
        """Speichert die aktuellen Tischkoordinaten als neuen, benannten Snapshot.

        Defensiver Guard gegen die Duplikat-Sperre zusätzlich zum deaktivierten
        Button (``_refresh_snapshot_table``) -- falls sich der Plan zwischen
        Refresh und Klick geändert haben sollte.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        if any(is_full_match(s, self.current_plan) for s in self.current_plan.snapshots):
            return
        name = simpledialog.askstring("Snapshot erstellen", "Name des Snapshots:", parent=self._snapshot_window)
        if name is None:
            return
        self._controller.dispatch(CreateSnapshotIntent(name=name))
        self._refresh_snapshot_table()

    def _load_selected_snapshot(self) -> None:
        """Stellt die Tischkoordinaten des ausgewählten Snapshots wieder her.

        No-Op, wenn der Snapshot bereits vollständig geladen ist. Entspricht
        der aktuelle Zustand selbst keinem vorhandenen Snapshot vollständig
        (würde also beim Laden ohne eigenen Snapshot verloren gehen), wird
        vorher bestätigt. Zeigt anschließend etwaige beim Deserialisieren
        aufgetretene Warnungen für genau diesen Snapshot (frisch von der
        Platte gelesen, s. ``load_snapshot_load_issues`` -- kein Cache).
        """
        if not self.current_plan or not self.current_plan_path:
            return
        snapshot_id = self._selected_snapshot_id()
        if snapshot_id is None:
            return
        snapshot = self.current_plan.snapshot_by_id(snapshot_id)
        if snapshot is None:
            return
        if is_full_match(snapshot, self.current_plan):
            return

        if not any(is_full_match(s, self.current_plan) for s in self.current_plan.snapshots):
            confirmed = messagebox.askyesno(
                "Snapshot laden",
                "Der aktuelle Sitzplan ist nicht als Snapshot gespeichert und geht beim Laden verloren. "
                "Trotzdem laden?",
                parent=self._snapshot_window,
            )
            if not confirmed:
                return

        issues = self.plan_repository.load_snapshot_load_issues(self.current_plan_path).get(snapshot_id, [])
        if issues:
            messagebox.showwarning(
                "Snapshot enthielt fehlerhafte Einträge",
                "\n".join(issue.detail for issue in issues),
                parent=self._snapshot_window,
            )

        self._controller.dispatch(RestoreSnapshotIntent(snapshot_id=snapshot_id))
        self._refresh_snapshot_table()

    def _rename_selected_snapshot(self) -> None:
        """Öffnet einen Namensprompt und benennt den ausgewählten Snapshot um."""
        if not self.current_plan:
            return
        snapshot_id = self._selected_snapshot_id()
        if snapshot_id is None:
            return
        snapshot = self.current_plan.snapshot_by_id(snapshot_id)
        if snapshot is None:
            return
        new_name = simpledialog.askstring(
            "Snapshot umbenennen", "Neuer Name:", parent=self._snapshot_window, initialvalue=snapshot.name
        )
        if new_name is None:
            return
        self._controller.dispatch(RenameSnapshotIntent(snapshot_id=snapshot_id, new_name=new_name))
        self._refresh_snapshot_table()

    def _delete_selected_snapshot(self) -> None:
        """Löscht den ausgewählten Snapshot nach Bestätigung; der aktuelle Sitzplan bleibt unverändert."""
        if not self.current_plan:
            return
        snapshot_id = self._selected_snapshot_id()
        if snapshot_id is None:
            return
        snapshot = self.current_plan.snapshot_by_id(snapshot_id)
        if snapshot is None:
            return
        if not self._controller.state.settings.hide_snapshot_delete_confirm:
            if not self._confirm_delete_snapshot_dialog(snapshot.name):
                return
        self._controller.dispatch(DeleteSnapshotIntent(snapshot_id=snapshot_id))
        self._refresh_snapshot_table()

    def _confirm_delete_snapshot_dialog(self, name: str) -> bool:
        """Zeigt einen Bestätigungsdialog mit "nicht mehr anzeigen"-Checkbox.

        Eigener kleiner Toplevel statt ``messagebox.askyesno``, da dieser
        keinen Checkbox-Slot hat. Ist die Checkbox bei Bestätigung angehakt,
        wird ``KartographSettings.hide_snapshot_delete_confirm`` persistiert.

        Args:
            name: Anzeigename des zu löschenden Snapshots.
        """
        result = {"confirmed": False}
        dialog = ui.Toplevel(self._snapshot_window)
        dialog.title("Snapshot löschen")
        dialog.transient(self._snapshot_window)
        dialog.resizable(False, False)

        tui.Label(
            dialog,
            text=f"Möchtest du den Snapshot '{name}' wirklich löschen?",
            wraplength=340,
            justify="left",
        ).pack(padx=16, pady=(16, 8), anchor="w")

        hide_var = ui.BooleanVar(value=False)
        Checkbox(dialog, text="Diese Warnung nicht mehr anzeigen", variable=hide_var).pack(
            padx=16, pady=(0, 12), anchor="w"
        )

        button_row = tui.Frame(dialog)
        button_row.pack(padx=16, pady=(0, 16), anchor="e")

        def _confirm() -> None:
            result["confirmed"] = True
            if hide_var.get():
                self._set_hide_snapshot_delete_confirm(True)
            dialog.destroy()

        def _cancel() -> None:
            dialog.destroy()

        tui.Button(button_row, text="Abbrechen", command=_cancel).pack(side="left", padx=(0, 8))
        tui.Button(button_row, text="Löschen", command=_confirm).pack(side="left")

        dialog.protocol("WM_DELETE_WINDOW", _cancel)
        dialog.grab_set()
        dialog.wait_window()
        return result["confirmed"]

    def _set_hide_snapshot_delete_confirm(self, value: bool) -> None:
        """Persistiert die "Löschen nicht mehr bestätigen"-Einstellung.

        Args:
            value: Neuer Zustand.
        """
        self._controller.dispatch(UpdateSettingsIntent(
            settings=dataclasses.replace(self._controller.state.settings, hide_snapshot_delete_confirm=value)
        ))
