"""Inhaltliche Guardrail-Checks (Shortcut-Integration, GUI-Contracts, Bridges).

Aus ``check_ai_guardrails.py`` ausgelagert (300-Zeilen-Regel), Inhalt unverändert.
"""

from __future__ import annotations

import ast
import os

from guardrail_config import (
    FUTURE_GUI_ENTRY_BASELINES,
    FUTURE_GUI_REQUIRED_SHARED_SNIPPETS,
    GUI_MIGRATION_BACKLOG_PATH,
    LAUFKERN_FALLBACK_SCAN_ROOTS,
    LEGACY_UI_BASECLASS_ALLOWLIST,
    ROOT,
    SHARED_PRIMITIVE_CLASS_ALLOWLIST,
    SHARED_PRIMITIVE_CLASS_NAMES,
)
from guardrail_support import (
    _contains_direct_tkinter_import,
    _forbid_substring,
    _iter_future_gui_entry_candidates,
    _iter_python_files_under,
    _iter_repo_gui_python_files,
    _local_ui_bases,
    _read,
    _read_entry_candidate_group,
    _read_main_window_module_group,
    _require_substring,
)


def _is_ci_environment() -> bool:
    """Return whether the check runs in a CI environment."""
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def _check_runtime_shortcut_integration(errors: list[str]) -> None:
    """Require runtime shortcut integration, overlay-stack popup gating and debug intents in GUI flow.

    Popup gating reads the bw-gui overlay stack (``blocking()``; menu popups do not block in
    Kartograph); toplevels register through ``_register_popup_window``. Until 2026-10-15 this
    rule required the former ``PopupPolicyRegistry`` (``tests/test_overlay_gating_tk.py``).

    Args:
        errors: Error list to append to when a required contract snippet is missing.
    """

    main_window = _read_main_window_module_group()
    source_label = "main_window.py (+ _mixin_*.py)"
    _require_substring(
        main_window,
        "self._runtime_shortcuts = KeybindingRegistry()",
        source_label,
        errors,
    )
    for snippet in ("return blocking(self.tk_root)()", "register_overlay(window, category, toplevel=window)"):
        _require_substring(main_window, snippet, source_label, errors)
    for stale in ("_sync_popup_sessions_from_windows", "PopupPolicyRegistry()", "_popup_registry"):
        if stale in main_window:
            errors.append(f"{source_label}: former popup registry/scan is back ({stale}); use the overlay stack")
    _require_substring(
        main_window,
        "self._runtime_shortcuts.evaluate_runtime(",
        source_label,
        errors,
    )
    _require_substring(
        main_window,
        "self._shortcut_binder = WindowShortcutBinder(",
        source_label,
        errors,
    )
    _require_substring(
        main_window,
        "def open_shortcut_runtime_debug_dialog(self) -> None:",
        source_label,
        errors,
    )

    intent_defs = _read("app/adapters/gui/ui_intents.py")
    _require_substring(
        intent_defs,
        "OPEN_SHORTCUT_RUNTIME_DEBUG",
        "ui_intents.py",
        errors,
    )
    _require_substring(
        intent_defs,
        "TOGGLE_SHORTCUT_RUNTIME_OFFLINE",
        "ui_intents.py",
        errors,
    )

    shortcut_mixin = _read("app/adapters/gui/_mixin_shortcuts.py")
    _require_substring(
        shortcut_mixin,
        "UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG: lambda: self.open_shortcut_runtime_debug_dialog(),",
        "_mixin_shortcuts.py",
        errors,
    )
    _require_substring(
        shortcut_mixin,
        "UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE: lambda: self.toggle_shortcut_runtime_offline(),",
        "_mixin_shortcuts.py",
        errors,
    )


def _check_shared_ui_contracts(errors: list[str]) -> None:
    """Require shared menu/dialog/tooltip contracts in main window (+ mixins).

    Args:
        errors: Error list to append to when a required or forbidden snippet check fails.
    """

    main_window = _read_main_window_module_group()
    source_label = "app/adapters/gui/main_window.py (+ _mixin_*.py)"

    required_snippets = (
        "from bw_gui.dialogs import open_tabbed_settings_dialog as open_shared_tabbed_settings_dialog",
        "from bw_gui.menu import section_spec",
        "def build_menu(self) -> list:",
        'section_spec("file", label="Datei", alt="d", items_provider=self._menu_items_file),',
        "from bw_gui.shortcuts import compose_hover_text as compose_shared_hover_text",
        "from bw_gui.widgets import HoverTooltip as SharedHoverTooltip",
        "tooltip = SharedHoverTooltip(widget, text, theme_key=self._shared_menu_theme_key())",
        "payload = open_shared_tabbed_settings_dialog(",
    )
    forbidden_snippets = (
        "except ModuleNotFoundError",
        "if SharedHoverTooltip is None",
        "if compose_shared_hover_text is None",
        "if open_shared_tabbed_settings_dialog is None",
    )

    for snippet in required_snippets:
        _require_substring(main_window, snippet, source_label, errors)
    for snippet in forbidden_snippets:
        _forbid_substring(main_window, snippet, source_label, errors)


def _check_future_gui_entry_contracts(errors: list[str]) -> None:
    """Require shared GUI bootstrap contracts for newly added entrypoint files.

    Args:
        errors: Error list to append to when a new entrypoint candidate fails a contract check.
    """

    for rel_path in _iter_future_gui_entry_candidates():
        if rel_path in FUTURE_GUI_ENTRY_BASELINES:
            continue

        text = _read_entry_candidate_group(rel_path)
        for snippet in FUTURE_GUI_REQUIRED_SHARED_SNIPPETS:
            _require_substring(text, snippet, rel_path, errors)

        _forbid_substring(text, "import tkinter", rel_path, errors)
        _forbid_substring(text, "from tkinter import", rel_path, errors)


def _check_repo_wide_gui_contracts(errors: list[str]) -> None:
    """Enforce repo-wide GUI contract: no direct tkinter imports and no new local widget bases.

    Args:
        errors: Error list to append to when a GUI source file violates the contract.
    """

    for rel_path in _iter_repo_gui_python_files():
        try:
            source = _read(rel_path).lstrip("\ufeff")
            module = ast.parse(source, filename=rel_path)
        except Exception as exc:
            errors.append(f"{rel_path}: failed to parse Python AST -> {exc}")
            continue

        if _contains_direct_tkinter_import(module):
            errors.append(
                f"{rel_path}: direct tkinter/ttk import is forbidden; use bw_gui.runtime and shared bw_gui modules"
            )

        for node in ast.walk(module):
            if not isinstance(node, ast.ClassDef):
                continue

            if node.name in SHARED_PRIMITIVE_CLASS_NAMES:
                marker = f"{rel_path}:{node.name}"
                if marker not in SHARED_PRIMITIVE_CLASS_ALLOWLIST:
                    errors.append(
                        f"{rel_path}:{node.lineno} class '{node.name}' redefines a reserved shared primitive; "
                        "import it from bw_gui.runtime/dialogs/widgets instead"
                    )

            bases = _local_ui_bases(node)
            if not bases:
                continue
            marker = f"{rel_path}:{node.name}"
            if marker in LEGACY_UI_BASECLASS_ALLOWLIST:
                continue
            errors.append(
                f"{rel_path}:{node.lineno} class '{node.name}' uses local UI base {bases}; "
                "move reusable widget implementation to bw-gui"
            )


def _check_gui_migration_backlog(errors: list[str]) -> None:
    """Require explicit backlog tracking for all active GUI exemption baselines/allowlists.

    Args:
        errors: Error list to append to when the backlog is missing a required entry.
    """

    backlog = _read(GUI_MIGRATION_BACKLOG_PATH)
    _require_substring(backlog, "## Active Exemptions", GUI_MIGRATION_BACKLOG_PATH, errors)
    _require_substring(backlog, "remove_by:", GUI_MIGRATION_BACKLOG_PATH, errors)

    for rel_path in sorted(FUTURE_GUI_ENTRY_BASELINES):
        _require_substring(backlog, f"- {rel_path}", GUI_MIGRATION_BACKLOG_PATH, errors)

    for marker in sorted(LEGACY_UI_BASECLASS_ALLOWLIST):
        _require_substring(backlog, f"- {marker}", GUI_MIGRATION_BACKLOG_PATH, errors)


def _check_laufkern_fallback_sunset(errors: list[str]) -> None:
    """Enforce Wave-3 fallback sunset: no ModuleNotFoundError fallback branch remains.

    Args:
        errors: Error list to append to when a forbidden fallback branch is found.
    """

    for rel_path in _iter_python_files_under(LAUFKERN_FALLBACK_SCAN_ROOTS):
        if "except ModuleNotFoundError" in _read(rel_path):
            errors.append(
                f"{rel_path}: ModuleNotFoundError fallback is forbidden in Wave-3; require shared imports without local fallback branches"
            )


def _check_ui_contract_bridge_decommission(errors: list[str]) -> None:
    """Phase-I decommission gate: ui_contract bridges stay thin shared re-export shims.

    Args:
        errors: Error list to append to when a bridge module fails the decommission contract.
    """

    required_imports = {
        "bw_libs/ui_contract/keybinding.py": "from bw_gui.contracts.keybinding import",
        "bw_libs/ui_contract/popup.py": "from bw_gui.contracts.popup import",
        "bw_libs/ui_contract/hsm.py": "from bw_gui.contracts.hsm import",
        "bw_libs/ui_contract/laufkern.py": "from bw_gui.laufkern import",
    }
    forbidden_local_markers = {
        "bw_libs/ui_contract/keybinding.py": ("class KeyBindingDefinition", "class KeybindingRegistry"),
        "bw_libs/ui_contract/popup.py": ("class PopupPolicy", "class PopupPolicyRegistry"),
        "bw_libs/ui_contract/hsm.py": ("class HsmContract", "def build_ui_hsm_contract"),
        "bw_libs/ui_contract/laufkern.py": ("class LaufKernManifest", "def aggregate_completion("),
    }

    for rel_path, import_marker in required_imports.items():
        source = _read(rel_path).lstrip("\ufeff")
        _require_substring(source, "ensure_bw_gui_on_path", rel_path, errors)
        _require_substring(source, import_marker, rel_path, errors)
        for forbidden in forbidden_local_markers[rel_path]:
            _forbid_substring(source, forbidden, rel_path, errors)


def _check_no_raw_tk_state_bitmasks(errors: list[str]) -> None:
    """Forbid app code from interpreting Tk ``event.state`` bits itself.

    Uses the central guard from bw-gui (``bw_gui.testing.tk_state_guard``) instead
    of a local copy.

    Args:
        errors: Error list to append one entry per offending file to.
    """
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from bw_libs.shared_gui_core import ensure_bw_gui_on_path

    ensure_bw_gui_on_path()
    from bw_gui.testing.tk_state_guard import RULE, find_offenders

    for rel_path, lines in find_offenders(ROOT / "app").items():
        errors.append(f"{rel_path}:{','.join(map(str, lines))}: {RULE}")
