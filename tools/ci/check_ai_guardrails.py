#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
import subprocess
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
        ),
        "shortcut_markers": (
            "<Control-comma>",
            "<Control-,>",
            "Strg+,",
        ),
    },
    {
        "label": "new-plan",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("NEW_PLAN", "plan.new"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.NEW_PLAN",),
    },
    {
        "label": "rename-selected-plan",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("RENAME_SELECTED_PLAN", "plan.rename_selected"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.RENAME_SELECTED_PLAN",),
    },
    {
        "label": "duplicate-selected-plan",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("DUPLICATE_SELECTED_PLAN", "plan.duplicate_selected"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.DUPLICATE_SELECTED_PLAN",),
    },
    {
        "label": "undo",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("UNDO", "edit.undo"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.UNDO",),
    },
    {
        "label": "redo",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("REDO", "edit.redo"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.REDO",),
    },
    {
        "label": "copy",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("COPY", "edit.copy"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.COPY",),
    },
    {
        "label": "cut",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("CUT", "edit.cut"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.CUT",),
    },
    {
        "label": "paste",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("PASTE", "edit.paste"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.PASTE",),
    },
    {
        "label": "escape",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("ESCAPE", "selection.clear"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.ESCAPE",),
    },
    {
        "label": "debug-runtime-overlay",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("OPEN_SHORTCUT_RUNTIME_DEBUG", "debug.shortcut.runtime.open"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
        "shortcut_markers": ("intent=UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG",),
    },
    {
        "label": "debug-runtime-offline",
        "intent_paths": ("app/adapters/gui/ui_intents.py",),
        "intent_markers": ("TOGGLE_SHORTCUT_RUNTIME_OFFLINE", "debug.shortcut.runtime.offline.toggle"),
        "shortcut_paths": ("app/adapters/gui/main_window.py",),
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


def _repo_root() -> Path:
    """Determine git repository root and fallback to local root path."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip())
    except Exception:
        return ROOT


def _staged_files(repo_root: Path) -> set[str]:
    """Return normalized staged paths relative to repository root.

    Args:
        repo_root: Root directory of the git repository to query.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        return {
            line.strip().replace("\\", "/")
            for line in result.stdout.splitlines()
            if line.strip()
        }
    except Exception:
        return set()


def _read(rel_path: str) -> str:
    """Read UTF-8 file from repo root and fail if required file is missing.

    Args:
        rel_path: Path relative to `ROOT` of the file to read.
    """
    path = ROOT / rel_path
    if not path.exists():
        raise RuntimeError(f"Missing required file: {rel_path}")
    return path.read_text(encoding="utf-8")


def _read_entry_candidate_group(rel_path: str) -> str:
    """Concatenate a GUI entrypoint file with its sibling `_mixin_*.py` modules.

    GUI entrypoints like main_window.py were split into per-concern mixins;
    a contract that used to live directly in the entrypoint file may now live
    in any of its sibling mixins.

    Args:
        rel_path: Path relative to `ROOT` of the GUI entrypoint file.
    """
    candidate_path = ROOT / rel_path
    texts = [_read(rel_path)]
    for sibling in sorted(candidate_path.parent.glob("_mixin_*.py")):
        texts.append(sibling.read_text(encoding="utf-8"))
    return "\n".join(texts)


def _read_main_window_module_group() -> str:
    """Concatenate main_window.py with its sibling `_mixin_*.py` modules."""
    return _read_entry_candidate_group("app/adapters/gui/main_window.py")


def _require_substring(text: str, needle: str, source: str, errors: list[str]) -> None:
    """Append guardrail error when required text fragment is missing.

    Args:
        text: Source text to search within.
        needle: Required substring that must be present in `text`.
        source: Label identifying the source of `text`, used in the error message.
        errors: Error list to append to when the check fails.
    """
    if needle not in text:
        errors.append(f"{source}: missing required text -> {needle}")


def _forbid_substring(text: str, needle: str, source: str, errors: list[str]) -> None:
    """Append guardrail error when deprecated fallback text is still present.

    Args:
        text: Source text to search within.
        needle: Forbidden substring that must not be present in `text`.
        source: Label identifying the source of `text`, used in the error message.
        errors: Error list to append to when the check fails.
    """
    if needle in text:
        errors.append(f"{source}: forbidden fallback text present -> {needle}")


def _is_future_gui_entry_path(rel_path: str) -> bool:
    """Return whether the path points to a guarded GUI entrypoint filename.

    Args:
        rel_path: Candidate path to check, relative to the repository root.
    """
    normalized = rel_path.replace("\\", "/")
    file_name = normalized.rsplit("/", 1)[-1]
    if file_name not in FUTURE_GUI_ENTRY_FILE_NAMES:
        return False
    return any(normalized.startswith(f"{root}/") for root in FUTURE_GUI_SEARCH_ROOTS)


def _iter_future_gui_entry_candidates() -> list[str]:
    """Collect GUI entrypoint candidates from configured GUI source roots."""
    candidates: set[str] = set()
    for rel_root in FUTURE_GUI_SEARCH_ROOTS:
        root_path = ROOT / rel_root
        if not root_path.exists():
            continue
        for file_path in root_path.rglob("*.py"):
            if file_path.name not in FUTURE_GUI_ENTRY_FILE_NAMES:
                continue
            candidates.add(file_path.relative_to(ROOT).as_posix())
    return sorted(candidates)


def _is_repo_gui_python_path(rel_path: str) -> bool:
    """Return whether a path belongs to repo-wide GUI python scan roots.

    Args:
        rel_path: Candidate path to check, relative to the repository root.
    """
    normalized = rel_path.replace("\\", "/")
    if not normalized.endswith(".py"):
        return False
    return any(normalized.startswith(f"{root}/") for root in GUI_CONTRACT_SCAN_ROOTS)


def _iter_repo_gui_python_files() -> list[str]:
    """Collect all GUI-related Python files under configured scan roots."""
    files: set[str] = set()
    for rel_root in GUI_CONTRACT_SCAN_ROOTS:
        root_path = ROOT / rel_root
        if not root_path.exists():
            continue
        for file_path in root_path.rglob("*.py"):
            files.add(file_path.relative_to(ROOT).as_posix())
    return sorted(files)


def _iter_python_files_under(rel_roots: tuple[str, ...]) -> list[str]:
    """Collect Python files under given roots relative to `ROOT`.

    Args:
        rel_roots: Root directories (relative to `ROOT`) to scan recursively.
    """

    files: set[str] = set()
    for rel_root in rel_roots:
        root_path = ROOT / rel_root
        if not root_path.exists():
            continue
        for file_path in root_path.rglob("*.py"):
            files.add(file_path.relative_to(ROOT).as_posix())
    return sorted(files)


def _contains_direct_tkinter_import(module: ast.Module) -> bool:
    """Detect direct tkinter/ttk imports in module-level imports.

    Args:
        module: Parsed AST module to inspect for forbidden imports.
    """
    for node in module.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "tkinter" or name.startswith("tkinter.") or name == "ttk":
                    return True
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if (
                module_name == "tkinter"
                or module_name.startswith("tkinter.")
                or module_name == "ttk"
            ):
                return True
    return False


def _local_ui_bases(class_node: ast.ClassDef) -> list[str]:
    """Return local UI base expressions like ui.Tk/widgets.Frame/tui.Frame.

    Args:
        class_node: Parsed AST class definition whose base classes are inspected.
    """
    bases: list[str] = []
    for base in class_node.bases:
        if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
            if base.value.id in UI_BASECLASS_MODULE_ALIASES:
                bases.append(ast.unparse(base))
    return bases


def _has_relevant_staged_changes(staged: set[str], repo_root: Path) -> bool:
    """Run guardrails only when staged changes touch relevant policy files.

    Args:
        staged: Staged file paths to check against the relevant policy paths.
        repo_root: Root directory of the git repository, used to resolve relative paths.
    """
    try:
        root_rel_to_repo = str(ROOT.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        root_rel_to_repo = ""

    normalized_relevant: set[str] = set()
    for rel in GUARDRAIL_RELEVANT_PATHS:
        rel_norm = rel.replace("\\", "/")
        normalized_relevant.add(rel_norm)
        if root_rel_to_repo not in {"", "."}:
            normalized_relevant.add(f"{root_rel_to_repo}/{rel_norm}")

    return any(
        path in normalized_relevant
        or _is_future_gui_entry_path(path)
        or _is_repo_gui_python_path(path)
        for path in staged
    )


def _check_development_log_updated(staged: set[str], errors: list[str]) -> None:
    """Require development log updates when feature or architecture files change.

    Args:
        staged: Staged file paths to inspect for feature/architecture changes.
        errors: Error list to append to when the development log is missing an update.
    """
    normalized = {path.replace("\\", "/") for path in staged}
    if not normalized:
        return

    if "docs/DEVELOPMENT_LOG.md" in normalized:
        return

    requires_log = any(
        path.startswith("app/")
        or path.startswith("bw_libs/")
        or path == "kartograph.py"
        or path == "docs/ARCHITEKTUR.md"
        for path in normalized
    )
    if requires_log:
        errors.append(
            "docs/DEVELOPMENT_LOG.md missing update: relevant feature/architecture changes require a same-cycle log entry"
        )


def _check_changelog_updated(staged: set[str], errors: list[str]) -> None:
    """Require changelog updates when user-facing code paths change.

    Args:
        staged: Staged file paths to inspect for user-facing changes.
        errors: Error list to append to when the changelog is missing an update.
    """
    normalized = {path.replace("\\", "/") for path in staged}
    if not normalized:
        return

    if "CHANGELOG.md" in normalized:
        return

    requires_changelog = any(
        path.startswith("app/adapters/gui/")
        or path.startswith("app/core/usecases/")
        or path.startswith("bw_libs/")
        or path == "kartograph.py"
        for path in normalized
    ) or any(path in CHANGELOG_CODEV_RELEVANT_PATHS for path in normalized)
    if requires_changelog:
        errors.append(
            "CHANGELOG.md missing update: user- or co-developer-relevant changes require a changelog entry"
        )


def _collect_process_guidance_warnings() -> list[str]:
    """Collect non-blocking warnings for commit/push process guidance drift."""
    warnings: list[str] = []
    sources = {
        "AGENTS.md": _read("AGENTS.md"),
        ".github/copilot-instructions.md": _read(".github/copilot-instructions.md"),
        ".github/pull_request_template.md": _read(".github/pull_request_template.md"),
    }

    for label, needle in PROCESS_GUIDANCE_RULES.items():
        if not any(needle in text for text in sources.values()):
            warnings.append(
                f"process-guidance ({label}) not found in governance docs/templates"
            )
    return warnings


def _has_any_marker(rel_paths: tuple[str, ...], markers: tuple[str, ...]) -> bool:
    """Return whether any marker appears in at least one existing source file.

    Args:
        rel_paths: Candidate file paths (relative to `ROOT`) to search.
        markers: Substrings to look for in each existing file's contents.
    """

    for rel_path in rel_paths:
        path = ROOT / rel_path
        if not path.exists():
            continue
        text = _read(rel_path)
        if any(marker in text for marker in markers):
            return True
    return False


def _collect_shortcut_coverage_warnings() -> list[str]:
    """Collect non-blocking warnings when key intents miss keyboard shortcut markers."""

    warnings: list[str] = []
    for check in SHORTCUT_COVERAGE_SOFT_CHECKS:
        intent_paths = tuple(check["intent_paths"])
        intent_markers = tuple(check["intent_markers"])
        shortcut_paths = tuple(check["shortcut_paths"])
        shortcut_markers = tuple(check["shortcut_markers"])
        if not _has_any_marker(intent_paths, intent_markers):
            continue
        if _has_any_marker(shortcut_paths, shortcut_markers):
            continue
        warnings.append(
            f"shortcut-coverage ({check['label']}): intent marker found without configured keyboard binding marker"
        )
    return warnings


def _is_ci_environment() -> bool:
    """Return whether the check runs in a CI environment."""
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def _check_runtime_shortcut_integration(errors: list[str]) -> None:
    """Require runtime shortcut integration and debug intents in GUI flow.

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
    _require_substring(
        main_window,
        "self._popup_registry = PopupPolicyRegistry()",
        source_label,
        errors,
    )
    _require_substring(
        main_window,
        "self._runtime_shortcuts.evaluate_runtime(",
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
        "from bw_gui.menu import CustomMenuBar as SharedCustomMenuBar",
        "from bw_gui.shortcuts import compose_hover_text as compose_shared_hover_text",
        "from bw_gui.widgets import HoverTooltip as SharedHoverTooltip",
        "self._shared_menu_bar = SharedCustomMenuBar(",
        "tooltip = SharedHoverTooltip(widget, text, theme_key=self._shared_menu_theme_key())",
        "payload = open_shared_tabbed_settings_dialog(",
    )
    forbidden_snippets = (
        "except ModuleNotFoundError",
        "if SharedCustomMenuBar is None",
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


def main() -> int:
    """Execute kartograph guardrail checks and return CI-compatible status code."""
    repo_root = _repo_root()
    staged = _staged_files(repo_root)
    if staged and not _has_relevant_staged_changes(staged, repo_root):
        print("AI guardrail check skipped (no guardrail-relevant staged files).")
        return 0

    errors: list[str] = []

    _read("AGENTS.md")
    _read(".github/copilot-instructions.md")
    _read(".github/pull_request_template.md")
    _read(".github/workflows/quality_checks.yml")
    _read(".github/workflows/release-from-changelog.yml")
    _read("docs/ARCHITEKTUR.md")
    _read("docs/DEVELOPMENT_LOG.md")
    _read("CHANGELOG.md")
    _read("bw_libs/ui_contract/keybinding.py")
    _read("bw_libs/ui_contract/popup.py")
    _read("bw_libs/ui_contract/hsm.py")
    _read("bw_libs/ui_contract/laufkern.py")
    _read("bw_libs/app_paths.py")

    architecture = _read("docs/ARCHITEKTUR.md")
    _require_substring(architecture, "aktuellen Ist-Zustand", "docs/ARCHITEKTUR.md", errors)

    changelog = _read("CHANGELOG.md")
    _require_substring(changelog, "## [Unreleased]", "CHANGELOG.md", errors)

    dev_log = _read("docs/DEVELOPMENT_LOG.md")
    _require_substring(dev_log, "## [Unreleased]", "docs/DEVELOPMENT_LOG.md", errors)

    _check_development_log_updated(staged, errors)
    _check_changelog_updated(staged, errors)
    _check_runtime_shortcut_integration(errors)
    _check_shared_ui_contracts(errors)
    _check_laufkern_fallback_sunset(errors)
    _check_ui_contract_bridge_decommission(errors)
    _check_future_gui_entry_contracts(errors)
    _check_repo_wide_gui_contracts(errors)
    _check_gui_migration_backlog(errors)
    warnings = _collect_process_guidance_warnings()
    warnings.extend(_collect_shortcut_coverage_warnings())

    if errors:
        print("AI guardrail check failed:")
        for item in errors:
            print(f" - {item}")
        return 2

    if warnings and not _is_ci_environment():
        print("AI guardrail process warnings (non-blocking):")
        for item in warnings:
            print(f" - {item}")

    print("AI guardrail check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
