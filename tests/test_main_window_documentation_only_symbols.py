"""Tests für _documentation_only_symbols als reine Ableitung (Bug 3 / kein Cache mehr)."""

from app.adapters.gui.main_window import KartographMainWindow
from app.core.domain.effective_symbol import EffectiveSymbol


def _window_with_effective_symbols(symbols: list[EffectiveSymbol]) -> KartographMainWindow:
    window = KartographMainWindow.__new__(KartographMainWindow)
    window.__dict__["effective_documentation_symbols"] = symbols
    return window


def test_derives_keys_of_all_effective_symbols_builtin_and_custom():
    symbols = [
        EffectiveSymbol(
            key="Nicht abgegeben / verweigert", glyph="X", display_name="Nicht abgegeben / verweigert",
            role="documentation_only", is_custom=False, legend=("a", "b", "c"), shortcut="x",
        ),
        EffectiveSymbol(
            key="abc123", glyph="★", display_name="Extra Fleiß",
            role="documentation_only", is_custom=True, legend=None, shortcut="L",
        ),
    ]
    window = _window_with_effective_symbols(symbols)

    assert window._documentation_only_symbols == {"Nicht abgegeben / verweigert", "abc123"}


def test_reflects_newly_added_custom_symbol_without_manual_rebuild_call():
    window = _window_with_effective_symbols([])
    assert window._documentation_only_symbols == set()

    window.effective_documentation_symbols.append(
        EffectiveSymbol(
            key="new-symbol-id", glyph="!", display_name="Neu",
            role="documentation_only", is_custom=True, legend=None, shortcut="L",
        )
    )

    assert "new-symbol-id" in window._documentation_only_symbols
