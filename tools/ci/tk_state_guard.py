"""AST-Guard: App-Code interpretiert Tk-Modifierbits (``event.state``) nicht selbst.

Gemeinsame Logik für ``tools/ci/check_ai_guardrails.py`` und
``tests/test_no_raw_tk_state_bitmasks.py`` -- eine Quelle statt zwei Kopien.

Hintergrund: Die Bedeutung von ``event.state`` ist plattformabhängig (unter Windows
ist ``0x0008`` NumLock, unter X11 Alt) und liegt ausschließlich im
bw-gui-Keybinding-Contract (``bw_gui.contracts.key_modifiers``). Gesucht wird genau
das Anti-Pattern ``<ausdruck>.state & ...`` bzw. ``getattr(<ausdruck>, "state") & ...``
(auch in ``int(...)`` gehüllt) -- beliebige andere Bitmasken bleiben erlaubt.
"""

from __future__ import annotations

import ast
from pathlib import Path

RULE = (
    "Apps interpretieren Tk-Modifierbits nicht selbst (plattformabhängig: unter Windows "
    "ist 0x0008 NumLock). Nutze den bw-gui-WindowShortcutBinder oder "
    "bw_gui.contracts.modifiers_from_event()."
)


def _is_state_access(node: ast.AST) -> bool:
    """True für ``x.state``, ``int(x.state)`` und ``getattr(x, "state"[, default])``."""
    if isinstance(node, ast.Attribute) and node.attr == "state":
        return True
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) >= 2:
            name = node.args[1]
            return isinstance(name, ast.Constant) and name.value == "state"
        if isinstance(func, ast.Name) and func.id == "int" and node.args:
            return _is_state_access(node.args[0])
    return False


def raw_state_bitmask_lines(path: Path) -> list[int]:
    """Zeilennummern in *path*, an denen ``state & ...`` ausgewertet wird."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
            if _is_state_access(node.left) or _is_state_access(node.right):
                lines.append(node.lineno)
    return lines


def find_offenders(app_root: Path) -> dict[str, list[int]]:
    """Alle Fundstellen unter *app_root* als ``{relativer Pfad: [Zeilen]}``."""
    return {
        str(path.relative_to(app_root.parent)): lines
        for path in sorted(app_root.rglob("*.py"))
        if (lines := raw_state_bitmask_lines(path))
    }
