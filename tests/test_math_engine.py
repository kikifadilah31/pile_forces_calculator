"""
Validation cases for the pure math engine (template Core 1).

Expected values are hand-calculated for a symmetric 4-pile group and cross-
checked against the closed-form rigid-cap distribution. Floats are compared
with np.isclose (never ==), tolerance from config.VALIDATION_RTOL.
"""

import numpy as np
import pytest

from pile_forces import config, math_engine

RTOL = config.VALIDATION_RTOL


# --- Geometry shared by the validation case ---------------------------------
# Piles at (0,0),(3,0),(0,3),(3,3) -> centroid (1.5,1.5), spacing 3 m.
X = np.array([0.0, 3.0, 0.0, 3.0])
Y = np.array([0.0, 0.0, 3.0, 3.0])


def test_self_weights():
    # W_pc = 5*5*1.5*24 = 900 ; W_soil = 5*5*1*18 = 450
    assert np.isclose(math_engine.calc_pilecap_weight(5, 5, 1.5, 24), 900.0, rtol=RTOL)
    assert np.isclose(math_engine.calc_soil_weight(5, 5, 1.0, 18), 450.0, rtol=RTOL)


def test_pile_area_and_weight():
    a_circle = math_engine.calc_pile_area("Circle", 0.6)
    assert np.isclose(a_circle, 0.25 * np.pi * 0.36, rtol=RTOL)
    a_square = math_engine.calc_pile_area("Square", 0.5)
    assert np.isclose(a_square, 0.25, rtol=RTOL)
    # W_pile = area * 20 * 24
    assert np.isclose(math_engine.calc_pile_weight(a_circle, 20, 24), a_circle * 480, rtol=RTOL)


def test_pile_area_bad_shape_raises():
    with pytest.raises(ValueError):
        math_engine.calc_pile_area("Triangle", 0.5)


def test_reaction_to_action_signs():
    fx, fy, fz, mx, my, mz = math_engine.convert_reactions_to_actions(100, 50, 1000, 200, 150, 80)
    assert (fx, fy, fz, mx, my, mz) == (-100, -50, 1000, -200, -150, -80)


def test_centroid_and_polar_inertia():
    x_c, y_c = math_engine.calc_centroid(X, Y)
    assert np.isclose(x_c, 1.5, rtol=RTOL) and np.isclose(y_c, 1.5, rtol=RTOL)
    x_rel, y_rel = math_engine.calc_relative_coords(X, Y, x_c, y_c)
    # Sum(x^2) = Sum(y^2) = 4 * 1.5^2 = 9 ; I_polar = 18
    assert np.isclose((x_rel ** 2).sum(), 9.0, rtol=RTOL)
    assert np.isclose(math_engine.calc_polar_inertia(x_rel, y_rel), 18.0, rtol=RTOL)


def test_axial_distribution_validation_case():
    """Hand-calc: P_total=2350, base=587.5, W_pile≈135.7168.

    P1 = 587.5 - 33.333 + 25 + 135.7168 = 714.883
    """
    x_c, y_c = 1.5, 1.5
    x_rel, y_rel = math_engine.calc_relative_coords(X, Y, x_c, y_c)
    w_pile = math_engine.calc_pile_weight(math_engine.calc_pile_area("Circle", 0.6), 20, 24)

    axial = math_engine.calc_axial_forces(
        fz_act=1000, mx_act=-200, my_act=-150, n_piles=4,
        x_rel=x_rel, y_rel=y_rel, sum_x_sq=9.0, sum_y_sq=9.0,
        w_pilecap=900.0, w_soil=450.0, w_pile=w_pile,
    )
    expected = np.array([714.883469, 664.883469, 781.550136, 731.550136])
    assert np.allclose(axial, expected, rtol=RTOL)


def test_lateral_distribution_validation_case():
    """Hand-calc LC1: Fx_act=-100, Fy_act=-50, Mz_act=-80, I_polar=18.

    P1: Hx = -25 - 6.667 = -31.667 ; Hy = -12.5 + 6.667 = -5.833
    """
    x_rel, y_rel = math_engine.calc_relative_coords(X, Y, 1.5, 1.5)
    hx, hy, h_res = math_engine.calc_lateral_forces(
        fx_act=-100, fy_act=-50, mz_act=-80, n_piles=4,
        x_rel=x_rel, y_rel=y_rel, i_polar=18.0,
    )
    assert np.isclose(hx[0], -31.666667, rtol=RTOL)
    assert np.isclose(hy[0], -5.833333, rtol=RTOL)
    assert np.allclose(h_res, np.sqrt(hx ** 2 + hy ** 2), rtol=RTOL)


def test_axial_ixy_asymmetric_group():
    """Asymmetric 3-pile triangle at (0,0),(2,0),(0,2); pure My=10, Mx=0.

    Centroid (2/3, 2/3): Ixx=Iyy=8/3, Ixy=-4/3, det=16/3.
    With Ixy: P = [-5, 5, 0] and BOTH equilibria hold (ΣP·x=My=10, ΣP·y=-Mx=0).
    Without Ixy (sum_xy=0) the classic per-axis form gives [-2.5, 5, -2.5] and
    VIOLATES ΣP·y=0 (spurious moment about x) — the reason the correction matters.
    """
    x_tri = np.array([0.0, 2.0, 0.0])
    y_tri = np.array([0.0, 0.0, 2.0])
    x_c, y_c = math_engine.calc_centroid(x_tri, y_tri)
    x_rel, y_rel = math_engine.calc_relative_coords(x_tri, y_tri, x_c, y_c)
    sum_x_sq = float((x_rel ** 2).sum())
    sum_y_sq = float((y_rel ** 2).sum())
    sum_xy = float((x_rel * y_rel).sum())

    kw = dict(
        fz_act=0.0, mx_act=0.0, my_act=10.0, n_piles=3,
        x_rel=x_rel, y_rel=y_rel, sum_x_sq=sum_x_sq, sum_y_sq=sum_y_sq,
        w_pilecap=0.0, w_soil=0.0, w_pile=0.0,
    )

    # With Ixy correction
    p_ixy = math_engine.calc_axial_forces(sum_xy=sum_xy, **kw)
    assert np.allclose(p_ixy, [-5.0, 5.0, 0.0], rtol=RTOL, atol=1e-9)
    assert np.isclose((p_ixy * x_rel).sum(), 10.0, rtol=RTOL)   # ΣP·x = My
    assert np.isclose((p_ixy * y_rel).sum(), 0.0, atol=1e-9)    # ΣP·y = -Mx = 0

    # Without Ixy (toggle off) — differs, and breaks the ΣP·y equilibrium
    p_noixy = math_engine.calc_axial_forces(sum_xy=0.0, **kw)
    assert np.allclose(p_noixy, [-2.5, 5.0, -2.5], rtol=RTOL, atol=1e-9)
    assert not np.isclose((p_noixy * y_rel).sum(), 0.0, atol=1e-6)


def test_calc_dcr_allowable():
    axial = np.array([1000.0, -200.0, 0.0])   # comp, tension, zero
    h_res = np.array([50.0, 40.0, 10.0])
    dc, dt, dl, dmax = math_engine.calc_dcr(axial, h_res, cap_comp=2000.0, cap_tens=400.0, cap_lat=80.0)
    assert np.allclose(dc, [0.5, 0.0, 0.0], rtol=RTOL)      # 1000/2000
    assert np.allclose(dt, [0.0, 0.5, 0.0], rtol=RTOL)      # 200/400
    assert np.allclose(dl, [0.625, 0.5, 0.125], rtol=RTOL)  # h/80
    assert np.allclose(dmax, [0.625, 0.5, 0.125], rtol=RTOL)


def test_calc_dcr_zero_capacity_ignored():
    # cap=0 means "not checked" -> that ratio is 0, never a division error
    dc, dt, dl, dmax = math_engine.calc_dcr(
        np.array([500.0]), np.array([100.0]), cap_comp=0.0, cap_tens=0.0, cap_lat=200.0,
    )
    assert dc[0] == 0.0 and dt[0] == 0.0
    assert np.isclose(dl[0], 0.5, rtol=RTOL)
    assert np.isclose(dmax[0], 0.5, rtol=RTOL)


def test_polygon_area_shoelace():
    # Unit square -> area 1.0 ; winding direction must not matter
    sq_x = np.array([0.0, 1.0, 1.0, 0.0])
    sq_y = np.array([0.0, 0.0, 1.0, 1.0])
    assert np.isclose(math_engine.polygon_area(sq_x, sq_y), 1.0, rtol=RTOL)
    assert np.isclose(math_engine.polygon_area(sq_x[::-1], sq_y[::-1]), 1.0, rtol=RTOL)
    # 3-4-5 right triangle -> area 6.0
    assert np.isclose(math_engine.polygon_area(np.array([0.0, 4.0, 0.0]), np.array([0.0, 0.0, 3.0])), 6.0, rtol=RTOL)


def test_rectangle_corners_closed_and_centered():
    rect = math_engine.rectangle_corners(1.5, 1.5, 5.0, 4.0)
    assert rect.shape == (5, 2)
    assert np.allclose(rect[0], rect[-1])          # closed ring
    assert np.isclose(rect[:, 0].min(), 1.5 - 2.5)  # length 5 spans X
    assert np.isclose(rect[:, 1].max(), 1.5 + 2.0)  # width 4 spans Y


def test_zero_division_single_line_geometry():
    """All piles on one line (y all equal) -> Sum(y^2)=0 -> Mx term drops to 0, no crash."""
    x = np.array([0.0, 1.0, 2.0])
    y = np.array([0.0, 0.0, 0.0])
    x_rel, y_rel = math_engine.calc_relative_coords(x, y, 1.0, 0.0)
    sum_x_sq = float((x_rel ** 2).sum())
    sum_y_sq = float((y_rel ** 2).sum())  # == 0
    axial = math_engine.calc_axial_forces(
        fz_act=300, mx_act=100, my_act=0, n_piles=3,
        x_rel=x_rel, y_rel=y_rel, sum_x_sq=sum_x_sq, sum_y_sq=sum_y_sq,
        w_pilecap=0.0, w_soil=0.0, w_pile=0.0,
    )
    assert np.all(np.isfinite(axial))
    # Base 100 each, no bending contribution since Sum(y^2)=0 and My=0
    assert np.allclose(axial, 100.0, rtol=RTOL)
