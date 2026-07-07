"""
Pure engineering math — stateless, vectorized, SI-family internal (kN, m).

This module is the numerical heart of the tool. It does NOT import pandas,
matplotlib, or argparse (template Core 7). All inputs/outputs are floats or
NumPy arrays.

Failure policy (Core 3): these functions do not represent "design failure"
(the elastic distribution always resolves), so they never return NaN.
Zero-division for degenerate geometries (e.g. all piles on one line) is
handled by returning a zero moment contribution about that axis, which is the
physically correct result (no resisting lever arm). Corrupt input is the
responsibility of `validators.py` (fail-fast), not this module.
"""

import numpy as np

from . import config

# ---------------------------------------------------------------------------
# Step 1: Self-Weight Calculations
# ---------------------------------------------------------------------------

def calc_pilecap_weight(length: float, width: float, height: float, gamma_concrete: float) -> float:
    """Pilecap self-weight [kN].

    W_pc = length[m] * width[m] * height[m] * gamma_concrete[kN/m^3]
    """
    return length * width * height * gamma_concrete


def calc_soil_weight(length: float, width: float, height_soil: float, gamma_soil: float) -> float:
    """Soil backfill weight resting on the pilecap [kN].

    W_soil = length[m] * width[m] * height_soil[m] * gamma_soil[kN/m^3]

    # TODO: subtract pier area from soil weight in a future update
    #       (currently conservative — uses full pilecap plan area).
    """
    return length * width * height_soil * gamma_soil


def calc_pile_area(shape: str, dimension: float) -> float:
    """Single pile cross-sectional area [m^2].

    Square: B^2 (dimension[m] = side width)
    Circle: 0.25 * pi * D^2 (dimension[m] = diameter)
    """
    if shape == "Square":
        return dimension ** 2
    if shape == "Circle":
        return 0.25 * np.pi * dimension ** 2
    raise ValueError(f"Unknown pile shape: {shape!r}. Use 'Square' or 'Circle'.")


def calc_pile_weight(area: float, length_pile: float, gamma_pile: float) -> float:
    """Single pile self-weight [kN].

    W_pile = area[m^2] * length_pile[m] * gamma_pile[kN/m^3]
    """
    return area * length_pile * gamma_pile


# ---------------------------------------------------------------------------
# Pilecap geometry (boundary + plan area)
# ---------------------------------------------------------------------------

def polygon_area(x: np.ndarray, y: np.ndarray) -> float:
    """Plan area [m^2] of a simple polygon via the shoelace formula.

    x, y : vertex coordinates [m] in order (open ring; closing edge implied).
    Returns the absolute area, so vertex winding (CW/CCW) does not matter.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def rectangle_corners(x_c: float, y_c: float, length: float, width: float) -> np.ndarray:
    """Closed rectangle polygon centered on (x_c, y_c) [m].

    length spans X, width spans Y. Returns a (5, 2) array (first vertex
    repeated at the end) ready to plot as a closed outline.
    """
    hl, hw = length / 2.0, width / 2.0
    return np.array([
        [x_c - hl, y_c - hw],
        [x_c + hl, y_c - hw],
        [x_c + hl, y_c + hw],
        [x_c - hl, y_c + hw],
        [x_c - hl, y_c - hw],
    ])


def close_polygon(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Return an (n+1, 2) closed ring from open vertex lists (repeats vertex 0)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    pts = np.column_stack([x, y])
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[0]])
    return pts


# ---------------------------------------------------------------------------
# Step 2: Reaction to Action Conversion
# ---------------------------------------------------------------------------

def convert_reactions_to_actions(
    fx: float, fy: float, fz: float, mx: float, my: float, mz: float,
) -> tuple[float, float, float, float, float, float]:
    """Convert Midas reaction forces to foundation action forces.

    Fx_act = -Fx, Fy_act = -Fy, Fz_act = +Fz (kept positive: downward
    compression is positive for foundation design), Mx/My/Mz negated.

    All values in kN / kN·m. Returns (Fx, Fy, Fz, Mx, My, Mz) actions.
    """
    return (-fx, -fy, fz, -mx, -my, -mz)


# ---------------------------------------------------------------------------
# Step 3: Centroid & Group Polar Inertia
# ---------------------------------------------------------------------------

def calc_centroid(x_coords: np.ndarray, y_coords: np.ndarray) -> tuple[float, float]:
    """Pile group centroid as the mean of coordinates [m].

    x_coords, y_coords : 1D arrays of global pile coordinates [m].
    """
    return float(np.mean(x_coords)), float(np.mean(y_coords))


def calc_relative_coords(
    x_coords: np.ndarray, y_coords: np.ndarray, x_c: float, y_c: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Relative coordinates of each pile from the centroid [m].

    x_i = X_global,i - X_c ; y_i = Y_global,i - Y_c
    """
    x_rel = np.asarray(x_coords, dtype=float) - x_c
    y_rel = np.asarray(y_coords, dtype=float) - y_c
    return x_rel, y_rel


def calc_polar_inertia(x_rel: np.ndarray, y_rel: np.ndarray) -> float:
    """Group polar moment of inertia [m^2].

    I_polar = Sum(x_i^2) + Sum(y_i^2)
    """
    x_rel = np.asarray(x_rel, dtype=float)
    y_rel = np.asarray(y_rel, dtype=float)
    return float((x_rel ** 2).sum() + (y_rel ** 2).sum())


# ---------------------------------------------------------------------------
# Step 4 & 5: Force Distribution (vectorized over piles)
# ---------------------------------------------------------------------------

def calc_axial_forces(
    fz_act: float,
    mx_act: float,
    my_act: float,
    n_piles: int,
    x_rel: np.ndarray,
    y_rel: np.ndarray,
    sum_x_sq: float,
    sum_y_sq: float,
    w_pilecap: float,
    w_soil: float,
    w_pile: float,
    sum_xy: float = 0.0,
) -> np.ndarray:
    """Axial force in each pile [kN] (vectorized).

    General biaxial-bending distribution for a rigid cap, including the pile
    group product of inertia (asymmetric / irregular layouts):

        Ixx = Sum(y^2), Iyy = Sum(x^2), Ixy = Sum(x*y), det = Ixx*Iyy - Ixy^2
        b = (My*Ixx + Mx*Ixy) / det        # coefficient of x_i
        c = (-Mx*Iyy - My*Ixy) / det       # coefficient of y_i
        P_axial,i = P_total/n + b*x_i + c*y_i + W_pile
    where P_total = Fz_act + W_pilecap + W_soil.

    When Ixy = 0 (symmetric group) this reduces exactly to the classic
    per-axis form  P/n - Mx*y_i/Sum(y^2) + My*x_i/Sum(x^2) + W_pile.
    Pass sum_xy=0.0 to force that reduced form (the `apply_ixy=False` toggle).

    Units: forces [kN], moments [kN·m], coordinates [m], weights [kN].
    Zero-division protection: falls back to the per-axis form when the coupled
    determinant is ~0 (degenerate single-line geometry).
    """
    p_total = fz_act + w_pilecap + w_soil
    axial_base = p_total / n_piles

    ixx = sum_y_sq  # second moment about x-axis (uses y distances)
    iyy = sum_x_sq  # second moment about y-axis (uses x distances)
    ixy = sum_xy
    det = ixx * iyy - ixy * ixy

    if det > config.ZERO_TOL:
        b = (my_act * ixx + mx_act * ixy) / det
        c = (-mx_act * iyy - my_act * ixy) / det
        moment_contrib = b * x_rel + c * y_rel
    else:
        # Degenerate geometry (e.g. collinear piles): drop each bending term
        # whose Sum(coord^2) vanishes — matches the original per-axis handling.
        denom_y = sum_y_sq if sum_y_sq > config.ZERO_TOL else 1.0
        denom_x = sum_x_sq if sum_x_sq > config.ZERO_TOL else 1.0
        mx_contrib = np.where(sum_y_sq > config.ZERO_TOL, -(mx_act * y_rel) / denom_y, 0.0)
        my_contrib = np.where(sum_x_sq > config.ZERO_TOL, (my_act * x_rel) / denom_x, 0.0)
        moment_contrib = mx_contrib + my_contrib

    return axial_base + moment_contrib + w_pile


def calc_lateral_forces(
    fx_act: float,
    fy_act: float,
    mz_act: float,
    n_piles: int,
    x_rel: np.ndarray,
    y_rel: np.ndarray,
    i_polar: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Lateral force distribution including torsion [kN] (vectorized).

    Hx_i = Fx_act/n - Mz_act*y_i / I_polar
    Hy_i = Fy_act/n + Mz_act*x_i / I_polar
    H_resultant,i = sqrt(Hx_i^2 + Hy_i^2)

    Units: forces [kN], torsion Mz [kN·m], coords [m], I_polar [m^2].
    Torsion terms drop to 0 when I_polar ~ 0. Returns (Hx, Hy, H_resultant).
    """
    hx_base = fx_act / n_piles
    hy_base = fy_act / n_piles

    denom = i_polar if i_polar > config.ZERO_TOL else 1.0  # zeroed by mask when degenerate
    mz_contrib_x = np.where(i_polar > config.ZERO_TOL, -(mz_act * y_rel) / denom, 0.0)
    mz_contrib_y = np.where(i_polar > config.ZERO_TOL, (mz_act * x_rel) / denom, 0.0)

    hx_arr = hx_base + mz_contrib_x
    hy_arr = hy_base + mz_contrib_y
    h_resultant = np.sqrt(hx_arr ** 2 + hy_arr ** 2)

    return hx_arr, hy_arr, h_resultant


# ---------------------------------------------------------------------------
# Capacity check — demand/capacity ratios (allowable-capacity basis)
# ---------------------------------------------------------------------------

def calc_dcr(
    axial: np.ndarray,
    h_resultant: np.ndarray,
    cap_comp: float,
    cap_tens: float,
    cap_lat: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Demand-capacity ratios against ALLOWABLE capacities (vectorized).

    DCR = demand / allowable_capacity (limit 1.0). All in kN so ratios are
    dimensionless. A capacity given as <= 0 means "not checked" -> that ratio
    is 0 (ignored in the max), never a division error.

    - dcr_comp : compression only (axial > 0), = axial / cap_comp
    - dcr_tens : tension only (axial < 0), = |axial| / cap_tens
    - dcr_lat  : = H_resultant / cap_lat
    - dcr_max  : element-wise max of the three

    Returns (dcr_comp, dcr_tens, dcr_lat, dcr_max).
    """
    axial = np.asarray(axial, dtype=float)
    h_resultant = np.asarray(h_resultant, dtype=float)

    dcr_comp = np.where(
        (cap_comp > 0) & (axial > 0), axial / (cap_comp if cap_comp > 0 else 1.0), 0.0,
    )
    dcr_tens = np.where(
        (cap_tens > 0) & (axial < 0), -axial / (cap_tens if cap_tens > 0 else 1.0), 0.0,
    )
    dcr_lat = np.where(
        cap_lat > 0, h_resultant / (cap_lat if cap_lat > 0 else 1.0), 0.0,
    )
    dcr_max = np.maximum.reduce([dcr_comp, dcr_tens, dcr_lat])
    return dcr_comp, dcr_tens, dcr_lat, dcr_max
