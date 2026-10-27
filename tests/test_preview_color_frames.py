"""Tests für Optionen und Rahmenlogik der Sitzplan-Vorschau (``preview_color_frames``)."""

from __future__ import annotations

import math

import pytest

from app.core.domain.preview_color_frames import (
    MAX_FRAME_FRACTION,
    PreviewOptions,
    frame_colors_outer_to_inner,
    frame_rings,
    inradius,
    inset_convex_polygon,
    selectable_color_keys,
)
from app.core.domain.seat_orientation import TEACHER_TOP
from app.core.usecases.v4.color_usecases import used_color_tags
from tests.conftest import make_plan, make_student

ORDER = ["gelb", "orange", "rot"]


def _options(selected: set[str], staggered: bool = True) -> PreviewOptions:
    """Optionen mit gegebener Farbauswahl."""
    return PreviewOptions(selected_colors=frozenset(selected), staggered=staggered)


def test_defaults_match_user_decision() -> None:
    """Vorbelegung ohne offene Vorschau: Lehrertisch oben, keine Farben, Staffelung an."""
    options = PreviewOptions()
    assert (options.orientation, options.selected_colors, options.staggered) == (TEACHER_TOP, frozenset(), True)


def test_staggered_lists_highest_outside_and_color_one_inside() -> None:
    """Gestaffelt: höchste Farbe außen (Index 0), Farbe 1 ganz innen."""
    result = frame_colors_outer_to_inner(["gelb", "rot", "orange"], ORDER, _options({"gelb", "orange", "rot"}))
    assert result == ["rot", "orange", "gelb"]


def test_unstaggered_shows_only_highest_selected_color() -> None:
    """Ohne Staffelung nur die höchste *gewählte* Farbe."""
    result = frame_colors_outer_to_inner(["gelb", "rot"], ORDER, _options({"gelb"}, staggered=False))
    assert result == ["gelb"]


def test_unselected_colors_are_ignored() -> None:
    """Nicht gewählte Farben erscheinen nicht; ohne Auswahl gibt es keinen Rahmen."""
    assert frame_colors_outer_to_inner(["gelb", "rot"], ORDER, _options({"rot"})) == ["rot"]
    assert frame_colors_outer_to_inner(["gelb", "rot"], ORDER, PreviewOptions()) == []


def test_selectable_colors_are_used_and_known_in_palette_order() -> None:
    """Wählbar sind nur vergebene, in der Palette bekannte Farben, in Palettenreihenfolge."""
    anna = make_student(x=1, y=0)
    anna.diagnostic.color_tags = ["rot", "altlast"]
    ben = make_student(x=2, y=0, first_name="Ben")
    ben.diagnostic.color_tags = ["gelb"]
    plan = make_plan(students=[anna, ben])

    assert selectable_color_keys(used_color_tags(plan), ORDER) == ["gelb", "rot"]


def _rotated_rect(cx: float, cy: float, w: float, h: float, degrees: float) -> list[tuple[float, float]]:
    """Rechteck w×h um (cx, cy), um *degrees* gedreht."""
    a = math.radians(degrees)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in corners]


@pytest.mark.parametrize("reverse", [False, True])
def test_inset_keeps_equal_distance_on_rotated_rectangle(reverse: bool) -> None:
    """Inset um d an einem gedrehten 4×2-Rechteck ergibt ein (4-2d)×(2-2d)-Rechteck, beide Umlaufsinne."""
    rect = _rotated_rect(10.0, 5.0, 4.0, 2.0, 30.0)
    if reverse:
        rect = rect[::-1]
    inner = inset_convex_polygon(rect, 0.25)
    sides = [math.dist(inner[i], inner[(i + 1) % 4]) for i in range(4)]
    assert sorted(sides) == pytest.approx([1.5, 1.5, 3.5, 3.5])


def test_inradius_of_rectangle_is_half_short_side() -> None:
    """Für Rechtecke ist der Inkreisradius die halbe kurze Seite."""
    assert inradius(_rotated_rect(0.0, 0.0, 4.0, 2.0, 45.0)) == pytest.approx(1.0)


def test_frame_rings_cap_total_width_for_many_colors() -> None:
    """Bei vielen Ringen wird die Breite gedeckelt, damit innen Platz für den Namen bleibt."""
    rect = _rotated_rect(0.0, 0.0, 4.0, 2.0, 0.0)
    width, rings = frame_rings(rect, count=9, preferred_width=1.0)
    assert len(rings) == 9
    assert width * 9 == pytest.approx(MAX_FRAME_FRACTION * 1.0)


def test_frame_rings_keep_preferred_width_when_space_allows() -> None:
    """Ist genug Platz, bleibt die Wunschbreite; ohne Ringe gibt es nichts."""
    rect = _rotated_rect(0.0, 0.0, 40.0, 20.0, 0.0)
    assert frame_rings(rect, count=2, preferred_width=1.5)[0] == pytest.approx(1.5)
    assert frame_rings(rect, count=0, preferred_width=1.5) == (0.0, [])
