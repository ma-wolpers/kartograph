#!/usr/bin/env python3
from __future__ import annotations

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
    "CHANGELOG.md",
    "tools/ci/check_ai_guardrails.py",
    "app/adapters/gui/keybinding_registry.py",
    "app/adapters/gui/popup_policy.py",
}
PROCESS_GUIDANCE_RULES = {
    "feature_commit": "Feature-Aenderungen werden in eigenstaendigen Commits",
    "manual_push": "Push erfolgt manuell",
}


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

    return any(path in normalized_relevant for path in staged)


def _check_development_log_updated(staged: set[str], errors: list[str]) -> None:
    """Require development log updates when feature or architecture files change."""
    normalized = {path.replace("\\", "/") for path in staged}
    if not normalized:
        return

    if "docs/DEVELOPMENT_LOG.md" in normalized:
        return

    requires_log = any(
        path.startswith("app/")
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
        or path == "kartograph.py"
        for path in normalized
    )
    if requires_changelog:
        errors.append("CHANGELOG.md missing update: user-facing changes require a changelog entry")


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
    _read("app/adapters/gui/keybinding_registry.py")
    _read("app/adapters/gui/popup_policy.py")

    architecture = _read("docs/ARCHITEKTUR.md")
    _require_substring(architecture, "aktuellen Ist-Zustand", "docs/ARCHITEKTUR.md", errors)

    changelog = _read("CHANGELOG.md")
    _require_substring(changelog, "## [Unreleased]", "CHANGELOG.md", errors)

    dev_log = _read("docs/DEVELOPMENT_LOG.md")
    _require_substring(dev_log, "## [Unreleased]", "docs/DEVELOPMENT_LOG.md", errors)

    _check_development_log_updated(staged, errors)
    _check_changelog_updated(staged, errors)
    warnings = _collect_process_guidance_warnings()

    if errors:
        print("AI guardrail check failed:")
        for item in errors:
            print(f" - {item}")
        return 2

    if warnings:
        print("AI guardrail process warnings (non-blocking):")
        for item in warnings:
            print(f" - {item}")

    print("AI guardrail check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
