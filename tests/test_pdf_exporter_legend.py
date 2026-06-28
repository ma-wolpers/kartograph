from __future__ import annotations

from app.core.domain.models_v4 import PaletteEntry
from app.infrastructure.exporters.pdf_exporter import PdfSeatingPlanExporter
from app.infrastructure.symbol_config_loader import SymbolDefinition
from tests.conftest import make_plan


class _FakeCanvas:
    def __init__(self) -> None:
        self.drawn_strings: list[str] = []

    def showPage(self) -> None:  # noqa: N802 - reportlab API style
        return

    def setFillColor(self, _color) -> None:  # noqa: N802 - reportlab API style
        return

    def setFont(self, _font_name: str, _font_size: int) -> None:  # noqa: N802 - reportlab API style
        return

    def drawString(self, _x: float, _y: float, text: str) -> None:  # noqa: N802 - reportlab API style
        self.drawn_strings.append(text)


class _FakeColors:
    black = object()

    @staticmethod
    def HexColor(value: str) -> str:  # noqa: N802 - reportlab API style
        return value


def _symbol_definition() -> SymbolDefinition:
    return SymbolDefinition(
        meaning="Beteiligung",
        glyph="☝",
        shortcut="b",
        legend_one="selten",
        legend_two="gelegentlich",
        legend_three="kontinuierlich",
    )


def test_legend_symbol_tables_create_separate_rows_per_level() -> None:
    exporter = PdfSeatingPlanExporter([_symbol_definition()])

    tables = exporter._legend_renderer._legend_symbol_tables({"Beteiligung": {1, 2, 3}})

    assert tables == [
        (
            "Beteiligung",
            [
                ("BBB", "kontinuierlich"),
                ("BB", "gelegentlich"),
                ("B", "selten"),
            ],
        )
    ]


def test_legend_page_does_not_draw_global_heading_when_tables_exist(monkeypatch) -> None:
    exporter = PdfSeatingPlanExporter([_symbol_definition()])
    canvas = _FakeCanvas()

    monkeypatch.setattr(exporter._legend_renderer, "_draw_wrapped_legend_table", lambda *args, **kwargs: 420.0)

    plan = make_plan()
    exporter._legend_renderer.render_legend_page(
        canvas,
        _FakeColors(),
        page_w=842.0,
        page_h=595.0,
        plan=plan,
        used_symbol_levels={"Beteiligung": {1}},
        used_colors=set(),
        include_color_markers=False,
    )

    assert all(not text.startswith("Legende:") for text in canvas.drawn_strings)


def test_legend_page_shows_empty_hint_when_used_colors_have_no_meanings() -> None:
    exporter = PdfSeatingPlanExporter([])
    canvas = _FakeCanvas()

    plan = make_plan()
    plan.color_palette = {
        "rot": PaletteEntry(label="Rot", hex="#f95738", meaning=""),
        "blau": PaletteEntry(label="Blau", hex="#1d3557", meaning="   "),
    }
    exporter._legend_renderer.render_legend_page(
        canvas,
        _FakeColors(),
        page_w=842.0,
        page_h=595.0,
        plan=plan,
        used_symbol_levels={},
        used_colors={"rot", "blau"},
        include_color_markers=True,
    )

    assert any("Keine Legendeninhalte" in text for text in canvas.drawn_strings)
