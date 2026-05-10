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
    "bw_libs/app_paths.py",
}
PROCESS_GUIDANCE_RULES = {
    "feature_commit": "Feature-Aenderungen werden in eigenstaendigen Commits",
    "manual_push": "Push erfolgt manuell",
}
CHANGELOG_CODEV_RELEVANT_PATHS = {
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    "tools/ci/check_ai_guardrails.py",
    "docs/GUI_MIGRATION_BACKLOG.md",
    "bw_libs/ui_contract/keybinding.py",
    "bw_libs/ui_contract/popup.py",
    "bw_libs/ui_contract/hsm.py",
    "bw_libs/app_paths.py",
}
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
    """Return normalized staged paths relative to repository root."""
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
    """Read UTF-8 file from repo root and fail if required file is missing."""
    path = ROOT / rel_path
    if not path.exists():
        raise RuntimeError(f"Missing required file: {rel_path}")
    return path.read_text(encoding="utf-8")


def _require_substring(text: str, needle: str, source: str, errors: list[str]) -> None:
    """Append guardrail error when required text fragment is missing."""
    if needle not in text:
        errors.append(f"{source}: missing required text -> {needle}")


def _forbid_substring(text: str, needle: str, source: str, errors: list[str]) -> None:
    """Append guardrail error when deprecated fallback text is still present."""
    if needle in text:
        errors.append(f"{source}: forbidden fallback text present -> {needle}")


def _is_future_gui_entry_path(rel_path: str) -> bool:
    """Return whether the path points to a guarded GUI entrypoint filename."""
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
    """Return whether a path belongs to repo-wide GUI python scan roots."""
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


def _contains_direct_tkinter_import(module: ast.Module) -> bool:
    """Detect direct tkinter/ttk imports in module-level imports."""
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
    """Return local UI base expressions like ui.Tk/widgets.Frame/tui.Frame."""
    bases: list[str] = []
    for base in class_node.bases:
        if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
            if base.value.id in UI_BASECLASS_MODULE_ALIASES:
                bases.append(ast.unparse(base))
    return bases


def _has_relevant_staged_changes(staged: set[str], repo_root: Path) -> bool:
    """Run guardrails only when staged changes touch relevant policy files."""
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
    """Require development log updates when feature or architecture files change."""
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
    """Require changelog updates when user-facing code paths change."""
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


def _is_ci_environment() -> bool:
    """Return whether the check runs in a CI environment."""
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def _check_runtime_shortcut_integration(errors: list[str]) -> None:
    """Require runtime shortcut integration and debug intents in GUI flow."""

    main_window = _read("app/adapters/gui/main_window.py")
    _require_substring(
        main_window,
        "self._runtime_shortcuts = KeybindingRegistry()",
        "main_window.py",
        errors,
    )
    _require_substring(
        main_window,
        "self._popup_registry = PopupPolicyRegistry()",
        "main_window.py",
        errors,
    )
    _require_substring(
        main_window,
        "self._runtime_shortcuts.evaluate_runtime(",
        "main_window.py",
        errors,
    )
    _require_substring(
        main_window,
        "def open_shortcut_runtime_debug_dialog(self) -> None:",
        "main_window.py",
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

    intent_controller = _read("app/adapters/gui/ui_intent_controller.py")
    _require_substring(
        intent_controller,
        "if intent == UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG:",
        "ui_intent_controller.py",
        errors,
    )
    _require_substring(
        intent_controller,
        "if intent == UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE:",
        "ui_intent_controller.py",
        errors,
    )


def _check_shared_ui_contracts(errors: list[str]) -> None:
    """Require shared menu/dialog/tooltip contracts in main window."""

    main_window = _read("app/adapters/gui/main_window.py")

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
        _require_substring(main_window, snippet, "app/adapters/gui/main_window.py", errors)
    for snippet in forbidden_snippets:
        _forbid_substring(main_window, snippet, "app/adapters/gui/main_window.py", errors)


def _check_future_gui_entry_contracts(errors: list[str]) -> None:
    """Require shared GUI bootstrap contracts for newly added entrypoint files."""

    for rel_path in _iter_future_gui_entry_candidates():
        if rel_path in FUTURE_GUI_ENTRY_BASELINES:
            continue

        text = _read(rel_path)
        for snippet in FUTURE_GUI_REQUIRED_SHARED_SNIPPETS:
            _require_substring(text, snippet, rel_path, errors)

        _forbid_substring(text, "import tkinter", rel_path, errors)
        _forbid_substring(text, "from tkinter import", rel_path, errors)


def _check_repo_wide_gui_contracts(errors: list[str]) -> None:
    """Enforce repo-wide GUI contract: no direct tkinter imports and no new local widget bases."""

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
    """Require explicit backlog tracking for all active GUI exemption baselines/allowlists."""

    backlog = _read(GUI_MIGRATION_BACKLOG_PATH)
    _require_substring(backlog, "## Active Exemptions", GUI_MIGRATION_BACKLOG_PATH, errors)
    _require_substring(backlog, "remove_by:", GUI_MIGRATION_BACKLOG_PATH, errors)

    for rel_path in sorted(FUTURE_GUI_ENTRY_BASELINES):
        _require_substring(backlog, f"- {rel_path}", GUI_MIGRATION_BACKLOG_PATH, errors)

    for marker in sorted(LEGACY_UI_BASECLASS_ALLOWLIST):
        _require_substring(backlog, f"- {marker}", GUI_MIGRATION_BACKLOG_PATH, errors)


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
    _check_future_gui_entry_contracts(errors)
    _check_repo_wide_gui_contracts(errors)
    _check_gui_migration_backlog(errors)
    warnings = _collect_process_guidance_warnings()

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
