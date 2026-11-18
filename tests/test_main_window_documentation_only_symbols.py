"""Tests für _documentation_only_symbols als reine Ableitung aus der Symbolsicht (kein eigener Cache)."""

from app.adapters.gui.main_window import KartographMainWindow
from app.core.domain.effective_symbol import EffectiveSymbol
from app.core.domain.symbol_view import SymbolView

BUILTIN = EffectiveSymbol(
    key="Nicht abgegeben / verweigert", glyph="X", display_name="Nicht abgegeben / verweigert",
    role="documentation_only", is_custom=False, legend=("a", "b", "c"), shortcut="x",
)
CUSTOM = EffectiveSymbol(
    key="abc123", glyph="★", display_name="Extra Fleiß",
    role="documentation_only", is_custom=True, legend=None, shortcut="L",
)


def _window_with_view(symbols: list[EffectiveSymbol]) -> KartographMainWindow:
    window = KartographMainWindow.__new__(KartographMainWindow)
    window.__dict__["_symbol_view"] = SymbolView(catalog=(), competences={}, documentation_symbols=tuple(symbols))
    return window


def test_derives_keys_of_all_effective_symbols_builtin_and_custom():
    window = _window_with_view([BUILTIN, CUSTOM])

    assert window._documentation_only_symbols == {"Nicht abgegeben / verweigert", "abc123"}


def test_follows_a_replaced_symbol_view_without_extra_cache():
    window = _window_with_view([])
    assert window._documentation_only_symbols == set()

    window.__dict__["_symbol_view"] = SymbolView(catalog=(), competences={}, documentation_symbols=(CUSTOM,))

    assert window._documentation_only_symbols == {"abc123"}
