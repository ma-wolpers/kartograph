"""Tests für den Architekturkarten-Generator (tools/docs/generate_architecture_map.py)."""

from __future__ import annotations

from html.parser import HTMLParser

import pytest

import tools.docs.generate_architecture_map as gam


@pytest.fixture(scope="module")
def data() -> dict:
    """Architekturdaten einmal pro Testmodul gegen den echten app/-Baum scannen."""
    return gam.build_data()


def test_build_data_finds_all_known_intents(data):
    """Alle 40 Intent-Klassen aus app/core/intents/ müssen im Katalog auftauchen."""
    names = {row["intent"] for row in data["intents"]}
    assert "DeleteStudentIntent" in names
    assert "CreatePlanIntent" in names
    assert len(names) == 40


def test_every_intent_has_a_resolved_handler(data):
    """_register_handlers() registriert aktuell jeden Intent mit einem Handler."""
    unresolved = [row["intent"] for row in data["intents"] if not row["handler"]]
    assert unresolved == []


def test_known_intent_handler_usecase_chain(data):
    """Stichprobe: DeleteStudentIntent -> handle_delete_student -> delete_student."""
    row = next(r for r in data["intents"] if r["intent"] == "DeleteStudentIntent")
    assert row["handler"] == "handle_delete_student"
    assert row["handler_path"] == "app/application/handlers/student_handlers.py"
    assert "delete_student" in row["usecases"]
    assert row["usecase_paths"]["delete_student"] == "app/core/usecases/v4/student_usecases.py"


def test_noop_handler_has_no_usecase(data):
    """ExportPdfIntent ist ein bewusster No-Op-Handler ohne Core-Usecase-Aufruf."""
    row = next(r for r in data["intents"] if r["intent"] == "ExportPdfIntent")
    assert row["handler"] == "handle_export_pdf"
    assert row["usecases"] == []


def test_mixin_composition_matches_main_window(data):
    """KartographMainWindow besteht aus genau 30 Mixins, alle gruppiert."""
    assert len(data["mixins"]) == 30
    assert all(m["group"] in gam.MIXIN_GROUP_ORDER for m in data["mixins"])
    classes = {m["cls"] for m in data["mixins"]}
    assert "CanvasEventsMixin" in classes


def test_legacy_vs_current_status_tagging(data):
    """v3-Module tragen status=legacy, ihre v4-Entsprechungen status=current."""
    by_path = {m["path"]: m for m in data["modules"]}
    assert by_path["app/core/domain/models.py"]["status"] == "legacy"
    assert by_path["app/core/domain/models_v4.py"]["status"] == "current"
    assert by_path["app/infrastructure/repositories/json_plan_repository.py"]["status"] == "legacy"
    assert by_path["app/infrastructure/repositories/v4/json_plan_repository_v4.py"]["status"] == "current"


def test_domain_model_tree_has_aggregate_root(data):
    """models_v4.py liefert SeatingPlan als Root mit den erwarteten Top-Level-Feldern."""
    model = data["model"]
    assert model["root"] == "SeatingPlan"
    field_names = {f[0] for f in model["classes"]["SeatingPlan"]["fields"]}
    assert {"meta", "classroom", "tablegroups", "color_palette", "documentation"} <= field_names
    legacy_names = {c["name"] for c in model["legacy"]}
    assert "Desk" in legacy_names


def test_generate_writes_well_formed_html(tmp_path):
    """generate() schreibt eine Datei mit ausgeglichenen Tags und gültigem eingebetteten JSON."""
    out = gam.generate(tmp_path / "architecture-map.html")
    html = out.read_text(encoding="utf-8")

    class _BalanceChecker(HTMLParser):
        VOID = {"meta", "link", "br", "img", "input", "hr"}

        def __init__(self) -> None:
            super().__init__()
            self.stack: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag not in self.VOID:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()

    checker = _BalanceChecker()
    checker.feed(html)
    assert checker.stack == []
    assert "DeleteStudentIntent" in html
    assert "handle_delete_student" in html
