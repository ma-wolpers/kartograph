"""Toggle-Sequenz-Regel für Diagnose- vs. Doku-Symbole.

Reine, GUI-unabhängige Funktion — der einzige Ort, an dem definiert ist,
welche Symbolstärken-Sequenz für welche Symbolrolle gilt. Sowohl der
Raster-Diagnose-Pfad (``symbol_usecases.py::toggle_diagnostic_symbol``) als
auch der gemeinsame Doku-Symbol-Toggle-Kern in der GUI
(``_toggle_documentation_symbol_for_student()``, genutzt von Dokuansicht,
Raster und dem katalogbasierten Leertaste-Kürzel gleichermaßen) rufen
ausschließlich diese Funktion auf, statt die Sequenz-Logik jeweils selbst
zusammenzubauen.
"""

from __future__ import annotations


def next_symbol_toggle_strength(current_strength: int, *, is_diagnostic: bool) -> int:
    """Berechnet die nächste Symbolstärke nach einem Toggle.

    Diagnosesymbole zyklen durch vier Schweregradstufen (0→1→2→3→0).
    Doku-Symbole — eingebaut wie eigene — sind reine Ein/Aus-Flags (0↔1).

    Args:
        current_strength: Aktuelle Stärke vor dem Toggle.
        is_diagnostic: True für Diagnosesymbole, False für Doku-Symbole
            (``role == "documentation_only"``, eingebaut oder eigen).

    Returns:
        Die nächste Stärke nach dem Toggle.
    """
    if is_diagnostic:
        return (current_strength + 1) % 4
    return 0 if current_strength > 0 else 1
