"""Tests für KartographSettings (Phase D1)."""

from app.core.domain.settings import DEFAULT_THEME_KEY, KartographSettings


class TestFromDict:
    def test_empty_payload_uses_defaults(self):
        settings = KartographSettings.from_dict({})
        assert settings == KartographSettings()

    def test_non_dict_payload_uses_defaults(self):
        settings = KartographSettings.from_dict(None)  # type: ignore[arg-type]
        assert settings == KartographSettings()

    def test_clamps_out_of_range_canvas_radius(self):
        settings = KartographSettings.from_dict({"canvas_radius": 9999})
        assert settings.canvas_radius == 50

    def test_invalid_canvas_radius_falls_back_to_default(self):
        settings = KartographSettings.from_dict({"canvas_radius": "not-a-number"})
        assert settings.canvas_radius == 50

    def test_invalid_grid_name_format_falls_back_to_default(self):
        settings = KartographSettings.from_dict({"grid_name_format": "Unbekanntes Format"})
        assert settings.grid_name_format == "Vorname Nachname"

    def test_theme_passthrough_for_arbitrary_string(self):
        # Validierung gegen die GUI-Theme-Registry bleibt Aufgabe der GUI.
        settings = KartographSettings.from_dict({"theme": "porcelain"})
        assert settings.theme == "porcelain"

    def test_blank_theme_falls_back_to_default(self):
        settings = KartographSettings.from_dict({"theme": "   "})
        assert settings.theme == DEFAULT_THEME_KEY

    def test_grid_visible_symbols_filters_blank_entries(self):
        settings = KartographSettings.from_dict({"grid_visible_symbols": ["Laptop", "  ", "Tablet"]})
        assert settings.grid_visible_symbols == ("Laptop", "Tablet")


class TestToDictRoundtrip:
    def test_roundtrip_preserves_values(self):
        settings = KartographSettings(
            plans_dir="C:/plans",
            theme="porcelain",
            canvas_radius=10,
            symbol_strength=2,
            viewport_follow_buffer=3,
            grid_name_format="Nachname",
            grid_visible_symbols=("Laptop",),
            details_overlay_position="left",
            tablegroup_overlay_position="bottom",
        )
        restored = KartographSettings.from_dict(settings.to_dict())
        assert restored == settings
