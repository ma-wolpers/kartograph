"""Gemeinsame Helfer der Kartograph-Guardrails: Repo/Git, Dateien lesen, AST-Abfragen.

Aus ``check_ai_guardrails.py`` ausgelagert (300-Zeilen-Regel), Inhalt unverändert.
"""

from __future__ import annotations

from pathlib import Path
import ast
import subprocess

from guardrail_config import (
    FUTURE_GUI_ENTRY_FILE_NAMES,
    FUTURE_GUI_SEARCH_ROOTS,
    GUI_CONTRACT_SCAN_ROOTS,
    ROOT,
    UI_BASECLASS_MODULE_ALIASES,
)


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
