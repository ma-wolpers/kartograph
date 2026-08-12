"""LaufKern-Tracking-Mixin für das Kartograph-Hauptfenster.

Stellt Tracking-Artefakte, das Runtime-Debug-Fenster sowie die
Overlay-Positions-Verwaltung für den Details-Container und die
Tischgruppen-Overlay bereit.
"""

from __future__ import annotations

import dataclasses

from app.adapters.gui.laufkern_manifest_provider import build_runtime_shortcut_manifest
from app.core.intents.view_intents import UpdateSettingsIntent
from bw_libs.ui_contract.keybinding import (
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    UI_MODE_PREVIEW,
)
from bw_libs.ui_contract.laufkern import aggregate_completion, emit_tracking_artifact, verify_manifest, verify_reachability
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui


class LaufkernMixin:
    """Mixin: LaufKern-Tracking, Shortcut-Runtime-Debug und Overlay-Positionen."""

    def _build_laufkern_manifest(self):
        """Erstellt ein deklaratives LaufKern-Manifest aus den registrierten Runtime-Shortcuts."""
        return build_runtime_shortcut_manifest(self._runtime_shortcuts)

    def _summarize_laufkern_reachability(self, *, context) -> str:
        """Gibt eine kompakte LaufKern-Erreichbarkeits-Zusammenfassung zurück.

        Args:
            context: Aktueller KeybindingRuntimeContext.

        Returns:
            Formatierter Status-String.
        """
        manifest = self._build_laufkern_manifest()
        manifest_ok, manifest_errors = verify_manifest(manifest)
        if not manifest_ok:
            return f"LaufKern manifest-errors={len(manifest_errors)}"
        results = verify_reachability(manifest=manifest, context=context)
        reachable = sum(1 for result in results if result.reachable)
        return f"LaufKern intents {reachable}/{len(results)} erreichbar"

    def _laufkern_step_id_for_intent(self, intent: str) -> str:
        """Gibt eine stabile Runtime-Tracking-Step-ID für einen Intent zurück.

        Args:
            intent: UiIntent-String.

        Returns:
            Stabiler Step-ID-String (z. B. ``"LK-D-RTC-001"``).
        """
        existing = self._laufkern_tracking_step_ids.get(intent)
        if existing is not None:
            return existing
        next_index = len(self._laufkern_tracking_step_ids) + 1
        step_id = f"LK-D-RTC-{next_index:03d}"
        self._laufkern_tracking_step_ids[intent] = step_id
        return step_id

    def _record_laufkern_intent_dispatch(self, intent: str, *, success: bool) -> None:
        """Zeichnet das Ergebnis einer Intent-Ausführung als LaufKern-Artefakt auf.

        Args:
            intent: Ausgeführter UiIntent-String.
            success: True wenn der Intent erfolgreich behandelt wurde.
        """
        self._laufkern_tracking_sequence += 1
        artifact = emit_tracking_artifact(
            run_id=self._laufkern_tracking_run_id,
            repo_name="kartograph",
            step_id=self._laufkern_step_id_for_intent(intent),
            phase="D",
            state="done" if success else "failed",
            sequence=self._laufkern_tracking_sequence,
            mandatory=True,
            producer="laufkern-runtime",
            evidence_ref=intent,
        )
        self._laufkern_tracking_artifacts.append(artifact)

    def _summarize_laufkern_completion(self) -> str:
        """Gibt eine kompakte Abschluss-Zusammenfassung der Tracking-Artefakte zurück.

        Returns:
            Formatierter Status-String.
        """
        if not self._laufkern_tracking_artifacts:
            return "LK completion n/a"
        summary = aggregate_completion(
            self._laufkern_tracking_artifacts,
            trusted_producers={"laufkern-runtime"},
        )
        return f"LK completion {summary.status} {summary.completed_steps}/{summary.mandatory_steps}"

    def toggle_shortcut_runtime_offline(self) -> None:
        """Schaltet den Offline-Simulationsmodus des Shortcut-Runtimes um."""
        self._shortcut_runtime_offline = not bool(self._shortcut_runtime_offline)
        self._shortcut_runtime_debug_offline_var.set(bool(self._shortcut_runtime_offline))
        self._refresh_shortcut_runtime_debug_dialog()

    def _on_shortcut_runtime_offline_var_changed(self) -> None:
        """Synchronisiert den Offline-Modus wenn die Checkbox geändert wird."""
        self._shortcut_runtime_offline = bool(self._shortcut_runtime_debug_offline_var.get())
        self._refresh_shortcut_runtime_debug_dialog()

    def open_shortcut_runtime_debug_dialog(self) -> None:
        """Öffnet das Shortcut-Runtime-Debug-Fenster oder bringt es in den Vordergrund."""
        if self._shortcut_runtime_debug_window is not None and int(self._shortcut_runtime_debug_window.winfo_exists()):
            self._refresh_shortcut_runtime_debug_dialog()
            self._shortcut_runtime_debug_window.deiconify()
            self._shortcut_runtime_debug_window.lift()
            self._shortcut_runtime_debug_window.focus_force()
            return

        window = ui.Toplevel(self)
        window.title("Shortcut Runtime Debug")
        window.geometry("980x520")
        window.minsize(820, 420)
        self._track_popup_window(window, policy_id="dialog.non_blocking")

        toolbar = tui.Frame(window, padding=(10, 8))
        toolbar.pack(fill="x")
        tui.Label(toolbar, textvariable=self._shortcut_runtime_debug_context_var, style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        offline_check = tui.Checkbutton(toolbar, text="Offline simulieren", variable=self._shortcut_runtime_debug_offline_var, command=self._on_shortcut_runtime_offline_var_changed)
        offline_check.pack(side="left", padx=(12, 0))
        self._attach_hover_help(offline_check, label="Offline-Modus fuer Runtime-Resolver umschalten", shortcut="Ctrl+Shift+O")
        refresh_button = tui.Button(toolbar, text="Aktualisieren", command=self._refresh_shortcut_runtime_debug_dialog)
        refresh_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(refresh_button, label="Runtime-Debug-Ansicht aktualisieren", shortcut=None)

        body = tui.Frame(window, padding=(10, 0, 10, 8))
        body.pack(fill="both", expand=True)
        columns = ("mode", "key", "binding", "status", "reason")
        table = tui.Treeview(body, columns=columns, show="headings")
        table.heading("mode", text="Mode")
        table.heading("key", text="Key")
        table.heading("binding", text="Binding")
        table.heading("status", text="Status")
        table.heading("reason", text="Reason")
        table.column("mode", width=100, anchor="center", stretch=False)
        table.column("key", width=130, anchor="center", stretch=False)
        table.column("binding", width=300, anchor="w", stretch=True)
        table.column("status", width=90, anchor="center", stretch=False)
        table.column("reason", width=180, anchor="w", stretch=True)
        table.pack(side="left", fill="both", expand=True)
        y_scroll = tui.Scrollbar(body, orient="vertical", command=table.yview)
        y_scroll.pack(side="right", fill="y")
        table.configure(yscrollcommand=y_scroll.set)
        tui.Label(window, textvariable=self._shortcut_runtime_debug_summary_var, style="Muted.TLabel").pack(fill="x", padx=10, pady=(0, 8))

        self._shortcut_runtime_debug_window = window
        self._shortcut_runtime_debug_table = table
        window.protocol("WM_DELETE_WINDOW", self._close_shortcut_runtime_debug_dialog)
        self._refresh_shortcut_runtime_debug_dialog()

    def _close_shortcut_runtime_debug_dialog(self) -> None:
        """Schließt das Runtime-Debug-Fenster und meldet es aus der Popup-Registry ab."""
        if self._shortcut_runtime_debug_window is not None and int(self._shortcut_runtime_debug_window.winfo_exists()):
            popup_id = str(self._shortcut_runtime_debug_window)
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)
            self._shortcut_runtime_debug_window.destroy()
        self._shortcut_runtime_debug_window = None
        self._shortcut_runtime_debug_table = None

    def _refresh_shortcut_runtime_debug_dialog(self) -> None:
        """Aktualisiert Tabelle und Statuszeile des Runtime-Debug-Fensters."""
        table = self._shortcut_runtime_debug_table
        if table is None:
            return

        context = self._build_runtime_context()
        self._shortcut_runtime_debug_context_var.set(
            f"mode={context.active_mode} | offline={context.offline} | dialog={context.dialog_open} | text-focus={context.text_input_focused}"
        )
        for item_id in table.get_children(""):
            table.delete(item_id)

        active_count = 0
        disabled_count = 0
        for mode in (UI_MODE_GLOBAL, UI_MODE_EDITOR, UI_MODE_PREVIEW, UI_MODE_DIALOG, UI_MODE_OFFLINE):
            for definition in self._runtime_shortcuts.all():
                if mode not in definition.modes and UI_MODE_GLOBAL not in definition.modes:
                    continue
                can_execute, reason = self._runtime_shortcuts.evaluate_runtime(definition, context, active_mode_override=mode)
                status = "active" if can_execute else "disabled"
                if can_execute:
                    active_count += 1
                else:
                    disabled_count += 1
                table.insert("", ui.END, values=(mode, definition.sequence, definition.binding_id, status, "" if can_execute else reason))

        total = active_count + disabled_count
        self._shortcut_runtime_debug_summary_var.set(
            " | ".join([
                f"Bindings: {total} total",
                f"{active_count} active",
                f"{disabled_count} disabled",
                self._summarize_laufkern_reachability(context=context),
                self._summarize_laufkern_completion(),
            ])
        )

    def _apply_details_overlay_position(self) -> None:
        """Ordnet Grid-Stack und Details-Container entsprechend der gespeicherten Overlay-Position an."""
        if not hasattr(self, "grid_stack"):
            return

        self.grid_stack.pack_forget()
        self.details_container.pack_forget()
        self.grid_container.pack_forget()
        self.x_scroll.pack_forget()
        self.grid_container.pack(fill="both", expand=True)
        self.x_scroll.pack(fill="x")

        position = self.details_overlay_position
        if position == "left":
            self.details_container.configure(width=560)
            self.details_container.pack_propagate(False)
            self.details_container.pack(side="left", fill="y", padx=(12, 8), pady=(0, 8))
            self.grid_stack.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=(0, 8))
            return
        if position == "right":
            self.details_container.configure(width=560)
            self.details_container.pack_propagate(False)
            self.grid_stack.pack(side="left", fill="both", expand=True, padx=(12, 8), pady=(0, 8))
            self.details_container.pack(side="left", fill="y", padx=(0, 12), pady=(0, 8))
            return

        self.details_container.pack_propagate(True)
        self.grid_stack.pack(fill="both", expand=True, padx=12, pady=(0, 0))
        self.details_container.pack(fill="x", padx=12, pady=(8, 12))

    def _on_details_overlay_position_changed(self) -> None:
        """Speichert die neue Details-Overlay-Position und ordnet die Widgets neu an."""
        self.details_overlay_position = self._normalize_details_overlay_position(self.details_overlay_position_var.get())
        self._controller.dispatch(UpdateSettingsIntent(
            settings=dataclasses.replace(self._controller.state.settings, details_overlay_position=self.details_overlay_position)
        ))
        self._apply_details_overlay_position()
        if self._details_panel_visible:
            fill_mode = "both" if self.details_overlay_position in {"left", "right"} else "x"
            self.details_frame.pack_forget()
            self.details_frame.pack(fill=fill_mode, padx=12, pady=(4, 12))
        self._refresh_details_panel()

    def _on_tablegroup_overlay_position_changed(self) -> None:
        """Speichert die neue Tischgruppen-Overlay-Position und positioniert das Overlay neu."""
        self.tablegroup_overlay_position = self._normalize_tablegroup_overlay_position(
            self.tablegroup_overlay_position_var.get()
        )
        self._controller.dispatch(UpdateSettingsIntent(
            settings=dataclasses.replace(self._controller.state.settings, tablegroup_overlay_position=self.tablegroup_overlay_position)
        ))
        self._position_tablegroup_overlay()
