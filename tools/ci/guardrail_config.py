"""Konfiguration der Kartograph-Guardrails (reine Daten, ``check_ai_guardrails.py``).

Pfadlisten, Marker und Allowlists, die die Checks in ``guardrail_checks.py`` und
``guardrail_process.py`` auswerten. Aus ``check_ai_guardrails.py`` ausgelagert
(300-Zeilen-Regel), Inhalt unverändert.
"""

# line-limit: data-only
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

GUARDRAIL_RELEVANT_PATHS = {
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    ".github/workflows/quality_checks.yml",
    ".github/workflows/release-from-changelog.yml",
    "docs/ARCHITEKTUR.md",
    "docs/DEVELOPMENT_LOG.md",
    "docs/GUI_MIGRATION_BACKLOG.md",
    "CHANGELOG.md",
    "tools/ci/check_ai_guardrails.py",
    "tools/ci/guardrail_checks.py",
    "tools/ci/guardrail_config.py",
    "tools/ci/guardrail_process.py",
    "tools/ci/guardrail_support.py",
    "app/adapters/gui/main_window.py",
    "bw_libs/ui_contract/keybinding.py",
    "bw_libs/ui_contract/popup.py",
    "bw_libs/ui_contract/hsm.py",
    "bw_libs/ui_contract/laufkern.py",
    "bw_libs/app_paths.py",
}
PROCESS_GUIDANCE_RULES = {
    "feature_commit": "Feature-Aenderungen werden in eigenstaendigen Commits",
    "manual_push": "Push erfolgt manuell",
}
SHORTCUT_COVERAGE_SOFT_CHECKS = (
    {
        "label": "open-settings",
        "intent_paths": (
            "app/adapters/gui/ui_intents.py",
            "app/adapters/gui/main_window.py",
        ),
        "intent_markers": (
            "OPEN_SETTINGS",
            "settings.open",
            "command=lambda: self._handle_intent(UiIntent.OPEN_SETTINGS)",
        ),
        "shortcut_paths": (
            "app/adapters/gui/main_window.py",
            "app/adapters/gui/_mixin_shortcut_bindings.py",
        ),
        "shortcut_markers": (
            '_k("Ctrl+,")',
            "Strg+,",
        ),
    },
    {
        "label": "new-plan",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("NEW_PLAN", "plan.new"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.NEW_PLAN",),
    },
    {
        "label": "rename-selected-plan",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("RENAME_SELECTED_PLAN", "plan.rename_selected"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.RENAME_SELECTED_PLAN",),
    },
    {
        "label": "duplicate-selected-plan",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("DUPLICATE_SELECTED_PLAN", "plan.duplicate_selected"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.DUPLICATE_SELECTED_PLAN",),
    },
    {
        "label": "undo",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("UNDO", "edit.undo"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.UNDO",),
    },
    {
        "label": "redo",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("REDO", "edit.redo"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.REDO",),
    },
    {
        "label": "copy",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("COPY", "edit.copy"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.COPY",),
    },
    {
        "label": "cut",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("CUT", "edit.cut"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.CUT",),
    },
    {
        "label": "paste",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("PASTE", "edit.paste"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.PASTE",),
    },
    {
        "label": "escape",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("ESCAPE", "selection.clear"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.ESCAPE",),
    },
    {
        "label": "debug-runtime-overlay",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("OPEN_SHORTCUT_RUNTIME_DEBUG", "debug.shortcut.runtime.open"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG",),
    },
    {
        "label": "debug-runtime-offline",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("TOGGLE_SHORTCUT_RUNTIME_OFFLINE", "debug.shortcut.runtime.offline.toggle"),
        "shortcut_paths": ("app/adapters/gui/main_window.py", "app/adapters/gui/_mixin_shortcut_bindings.py"),
        "shortcut_markers": ("intent=UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE",),
    },
)
CHANGELOG_CODEV_RELEVANT_PATHS = {
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    "tools/ci/check_ai_guardrails.py",
    "docs/GUI_MIGRATION_BACKLOG.md",
    "bw_libs/ui_contract/keybinding.py",
    "bw_libs/ui_contract/popup.py",
    "bw_libs/ui_contract/hsm.py",
    "bw_libs/ui_contract/laufkern.py",
    "bw_libs/app_paths.py",
}
LAUFKERN_BRIDGE_PATH = "bw_libs/ui_contract/laufkern.py"
LAUFKERN_FALLBACK_SCAN_ROOTS = ("app", "bw_libs")
FUTURE_GUI_SEARCH_ROOTS = (
    "app/adapters/gui",
    "app/ui",
)
FUTURE_GUI_ENTRY_FILE_NAMES = {
    "main_window.py",
    "ui.py",
    "blatt_ui.py",
    "screen_builder.py",
}
FUTURE_GUI_ENTRY_BASELINES: set[str] = set()
FUTURE_GUI_REQUIRED_SHARED_SNIPPETS = (
    "ensure_bw_gui_on_path()",
    "from bw_gui.runtime import",
    "from bw_gui.menu import",
    "open_tabbed_settings_dialog",
    "compose_hover_text",
    "HoverTooltip",
)
GUI_CONTRACT_SCAN_ROOTS = (*FUTURE_GUI_SEARCH_ROOTS, "bw_libs")
UI_BASECLASS_MODULE_ALIASES = {"ui", "widgets", "tui"}
LEGACY_UI_BASECLASS_ALLOWLIST: set[str] = set()
SHARED_PRIMITIVE_CLASS_NAMES = {"TkRootHost", "ScrollablePopupWindow", "WrappedTextField"}
SHARED_PRIMITIVE_CLASS_ALLOWLIST: set[str] = set()
GUI_MIGRATION_BACKLOG_PATH = "docs/GUI_MIGRATION_BACKLOG.md"
