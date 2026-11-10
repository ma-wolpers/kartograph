"""Menüs und Tooltips schreiben keine Tastennamen als Text (eine Quelle: die Bindung).

Die Taste kommt aus der Laufzeit-Registry (``_menu_label``, ``_attach_hover_help(intent=)``)
oder aus der lokalen Bindung (``_local_keys.ENTER``/``ESCAPE``). Ein Text wie
``shortcut="Ctrl+N"`` oder ``label="Neu (Strg+N)"`` veraltet beim Umbelegen still.
"""

from __future__ import annotations

import re
from pathlib import Path

GUI = Path(__file__).resolve().parents[1] / "app" / "adapters" / "gui"
_SHORTCUT_LITERAL = re.compile(r'shortcut="[^"]+"')
_KEY_IN_LABEL = re.compile(r'label="[^"]*\((?:Strg|Ctrl|Shift|Alt|Entf|Esc|Enter|F\d{1,2})\b[^"]*\)"')


def test_no_key_names_as_text_in_menus_or_tooltips():
    hits = [
        f"{path.name}:{number}: {line.strip()}"
        for path in sorted(GUI.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if _SHORTCUT_LITERAL.search(line) or _KEY_IN_LABEL.search(line)
    ]
    assert hits == []
