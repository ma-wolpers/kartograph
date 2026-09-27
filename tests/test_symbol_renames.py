"""Tests für die Migration umbenannter Symbolschlüssel ("Mathem. Fachkompetenz" → "Fachkompetenz").

Erfasste Einträge unter dem alten Bedeutungstext dürfen beim Laden nicht
verloren gehen — weder im Diagnoseprofil, in Doku-Einträgen noch im
Raster-Symbolfilter der Einstellungen.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.domain.models_v4 import Session, SessionEntry
from app.core.domain.settings import KartographSettings
from app.core.domain.symbol_renames import canonical_symbol_name, merge_symbol_strength
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan
from app.infrastructure.symbol_config_loader import load_symbol_definitions
from tests.conftest import make_plan, make_student

OLD = "Mathem. Fachkompetenz"
NEW = "Fachkompetenz"


def _reload(plan):
    return deserialize_plan(json.loads(json.dumps(serialize_plan(plan), ensure_ascii=False)))


class TestCanonicalName:
    def test_old_name_maps_to_new(self):
        assert canonical_symbol_name(OLD) == NEW

    def test_other_names_unchanged(self):
        assert canonical_symbol_name("Beteiligung") == "Beteiligung"
        assert canonical_symbol_name(NEW) == NEW

    def test_merge_keeps_higher_strength_on_collision(self):
        symbols: dict[str, int] = {}
        merge_symbol_strength(symbols, NEW, 1)
        merge_symbol_strength(symbols, OLD, 3)
        assert symbols == {NEW: 3}


class TestPlanMigration:
    def test_diagnostic_profile_symbol_is_migrated(self):
        student = make_student()
        student.diagnostic.symbols[OLD] = 2
        loaded = _reload(make_plan(students=[student]))
        assert loaded.classroom.students[0].diagnostic.symbols == {NEW: 2}

    def test_session_entry_symbol_is_migrated(self):
        student = make_student()
        plan = make_plan(students=[student])
        entry = SessionEntry()
        entry.symbols[OLD] = 3
        entry.symbols["Beteiligung"] = 1
        plan.documentation.sessions.append(Session(date="2026-01-01", entries={student.student_id: entry}))
        loaded = _reload(plan)
        loaded_entry = loaded.documentation.sessions[0].entries[student.student_id]
        assert loaded_entry.symbols == {NEW: 3, "Beteiligung": 1}


class TestSettingsMigration:
    def test_grid_visible_symbols_are_migrated_and_deduplicated(self):
        settings = KartographSettings.from_dict({"grid_visible_symbols": [OLD, "Beteiligung", NEW]})
        assert settings.grid_visible_symbols == (NEW, "Beteiligung")


def test_catalog_contains_new_name_only():
    definitions, error = load_symbol_definitions(Path("config/symbols.json"))
    assert error is None
    meanings = [d.meaning for d in definitions]
    assert NEW in meanings
    assert OLD not in meanings
