"""Prozess-Guardrails: relevante Staged-Änderungen, Changelog/Dev-Log, Hinweise.

Aus ``check_ai_guardrails.py`` ausgelagert (300-Zeilen-Regel), Inhalt unverändert.
"""

from __future__ import annotations

from pathlib import Path

from guardrail_config import (
    CHANGELOG_CODEV_RELEVANT_PATHS,
    GUARDRAIL_RELEVANT_PATHS,
    PROCESS_GUIDANCE_RULES,
    ROOT,
    SHORTCUT_COVERAGE_SOFT_CHECKS,
)
from guardrail_support import _is_future_gui_entry_path, _is_repo_gui_python_path, _read


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
