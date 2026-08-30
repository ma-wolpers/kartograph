"""Tests für die Toggle-Sequenz-Regel (Diagnose zykelt, Doku ist binär)."""

from app.core.domain.symbol_toggle import next_symbol_toggle_strength


class TestDiagnosticCycle:
    def test_cycles_through_all_four_stages_and_back_to_zero(self):
        strength = 0
        for expected in [1, 2, 3, 0]:
            strength = next_symbol_toggle_strength(strength, is_diagnostic=True)
            assert strength == expected


class TestDocumentationBinaryToggle:
    def test_zero_goes_to_one(self):
        assert next_symbol_toggle_strength(0, is_diagnostic=False) == 1

    def test_any_nonzero_strength_goes_back_to_zero(self):
        for current in [1, 2, 3]:
            assert next_symbol_toggle_strength(current, is_diagnostic=False) == 0
