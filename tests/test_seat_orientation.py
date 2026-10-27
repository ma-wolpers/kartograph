"""Tests für Ansicht-Drehung und Bounding-Box in ``app/core/domain/seat_orientation.py``."""

from __future__ import annotations

import pytest

from app.core.domain.seat_orientation import (
    ORIENTATION_MODES,
    TEACHER_BOTTOM,
    TEACHER_TOP,
    is_orientation_mode,
    orient_geometries,
    orient_point,
    world_bounds,
)
from app.core.domain.table_groups import SeatGeometryV4


def _geometry(cx: float, cy: float) -> SeatGeometryV4:
    """Baut eine achsenparallele Einheits-Tischgeometrie um ``(cx, cy)``."""
    polygon = ((cx - 0.5, cy - 0.5), (cx + 0.5, cy - 0.5), (cx + 0.5, cy + 0.5), (cx - 0.5, cy + 0.5))
    return SeatGeometryV4(
        x=int(cx), y=int(cy), is_teacher=False, group_id=None,
        center_x=cx, center_y=cy, polygon=polygon, student=None,
    )


def test_orientation_modes_are_the_known_keys() -> None:
    """Genau die zwei Ansichten, beide als gültig erkannt, Unbekanntes nicht."""
    assert [key for key, _label in ORIENTATION_MODES] == [TEACHER_BOTTOM, TEACHER_TOP]
    assert is_orientation_mode(TEACHER_TOP)
    assert not is_orientation_mode("sideways")


def test_orient_point_rotates_180_only_for_teacher_top() -> None:
    """``teacher_top`` spiegelt am Ursprung, ``teacher_bottom`` lässt unverändert."""
    assert orient_point(2.0, -3.0, TEACHER_TOP) == (-2.0, 3.0)
    assert orient_point(2.0, -3.0, TEACHER_BOTTOM) == (2.0, -3.0)


def test_orient_geometries_rotates_polygon_and_center_and_keeps_geometry() -> None:
    """Polygon und Mittelpunkt werden gedreht, die Ursprungsgeometrie bleibt erhalten."""
    geometry = _geometry(1.5, 2.5)
    (seat,) = orient_geometries([geometry], TEACHER_TOP)
    assert seat.center == (-1.5, -2.5)
    assert seat.polygon[0] == (-1.0, -2.0)
    assert seat.geometry is geometry


def test_world_bounds_spans_all_points() -> None:
    """Die Box umfasst alle Eckpunkte aller Polygone."""
    bounds = world_bounds([_geometry(0.5, 0.5).polygon, _geometry(3.5, 1.5).polygon])
    assert (bounds.min_x, bounds.min_y, bounds.span_x, bounds.span_y) == (0.0, 0.0, 4.0, 2.0)


def test_world_bounds_clamps_degenerate_span() -> None:
    """Eine entartete Box (alle Punkte gleich) bekommt die Mindestspanne 0.1."""
    bounds = world_bounds([((1.0, 1.0), (1.0, 1.0))])
    assert bounds.span_x == pytest.approx(0.1)
    assert bounds.span_y == pytest.approx(0.1)


def test_world_bounds_rejects_empty_input() -> None:
    """Ohne Punkte gibt es keine Box."""
    with pytest.raises(ValueError):
        world_bounds([])
