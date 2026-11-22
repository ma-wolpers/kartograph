"""Tests für die Bereichsregeln der Datenansicht (``core/domain/data_view_areas``) und ihre Speicherung."""

from __future__ import annotations

from app.core.domain.data_view_areas import (
    DEFAULT_VISIBLE_AREAS,
    DataArea,
    can_enable,
    normalize_visible_areas,
    shown_areas,
    visible_areas_for,
    with_area,
)
from app.core.domain.settings import KartographSettings

DOKU, NOTIZEN, NOTEN = DataArea.DOKU, DataArea.NOTIZEN, DataArea.NOTEN


class TestRules:
    def test_names_are_not_toggleable_and_always_shown_first(self):
        assert not DataArea.NAMEN.toggleable
        assert shown_areas((NOTEN, NOTIZEN)) == (DataArea.NAMEN, NOTIZEN, NOTEN)
        assert shown_areas(()) == (DataArea.NAMEN,)

    def test_normalize_orders_dedupes_drops_unknown_and_caps_at_two(self):
        assert normalize_visible_areas(["noten", "doku", "noten", "quatsch", "namen"]) == (DOKU, NOTEN)
        assert normalize_visible_areas(["noten", "notizen", "doku"]) == (DOKU, NOTIZEN)

    def test_third_area_cannot_be_enabled(self):
        assert not can_enable(NOTIZEN, (DOKU, NOTEN))
        assert can_enable(NOTEN, (DOKU, NOTEN))
        assert can_enable(NOTIZEN, (DOKU,))
        assert with_area((DOKU, NOTEN), NOTIZEN, True) == (DOKU, NOTEN)

    def test_toggling(self):
        assert with_area((DOKU, NOTEN), DOKU, False) == (NOTEN,)
        assert with_area((NOTEN,), NOTIZEN, True) == (NOTIZEN, NOTEN)
        assert with_area((NOTEN,), NOTEN, False) == ()


class TestStorage:
    def test_missing_plan_uses_default_but_empty_means_all_hidden(self):
        stored = {"p1": ()}
        assert visible_areas_for(stored, "p1") == ()
        assert visible_areas_for(stored, "p2") == DEFAULT_VISIBLE_AREAS

    def test_settings_roundtrip_per_plan(self):
        settings = KartographSettings().with_data_view_areas("p1", (NOTIZEN, NOTEN)).with_data_view_areas("p2", ())
        payload = settings.to_dict()
        assert payload["data_view_areas"] == {"p1": ["notizen", "noten"], "p2": []}
        assert KartographSettings.from_dict(payload).data_view_areas == {"p1": (NOTIZEN, NOTEN), "p2": ()}

    def test_invalid_stored_values_are_ignored(self):
        settings = KartographSettings.from_dict({"data_view_areas": {"p1": "doku", "": ["doku"], "p2": ["noten", 3]}})
        assert settings.data_view_areas == {"p2": (NOTEN,)}
        assert KartographSettings.from_dict({"data_view_areas": []}).data_view_areas == {}
