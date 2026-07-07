"""
Domain orchestration for pile-group force distribution.

Combines the pure formulas in `math_engine` with the tabular data model
(pandas). Produces the master output table (Load Cases x Piles) and the
governing-load-case envelope. All values in kN / m (internal unit system).
"""

import pandas as pd

from . import math_engine


def build_master_output(
    df_piles: pd.DataFrame,
    df_lc: pd.DataFrame,
    params: dict,
    pilecap_poly: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the master output table by cross-joining Load Cases x Piles.

    Parameters
    ----------
    df_piles : DataFrame [Pile_ID, X, Y]  (X, Y in m)
    df_lc : DataFrame [LC_ID, Fx, Fy, Fz, Mx, My, Mz]  (raw Midas reactions, kN / kN·m)
    params : design parameters (see config.DEFAULT_PARAMS)
    pilecap_poly : optional DataFrame [X, Y] of custom pilecap polygon vertices.
        When given (irregular pilecap), the pilecap concrete AND soil weights
        use the polygon's actual plan area instead of pilecap_length × width,
        keeping the drawn boundary and the computed weight consistent.

    Returns
    -------
    DataFrame [LC_ID, Pile_ID, X, Y, Axial_Force, Hx, Hy, H_Resultant] in kN.
    """
    # --- Plan area (m^2): custom polygon area if given, else length × width ---
    if pilecap_poly is not None:
        plan_area = math_engine.polygon_area(
            pilecap_poly["X"].to_numpy(dtype=float), pilecap_poly["Y"].to_numpy(dtype=float),
        )
    else:
        plan_area = params["pilecap_length"] * params["pilecap_width"]

    # --- Self-weights (kN) — area × thickness × unit weight ---
    w_pilecap = plan_area * params["pilecap_height"] * params["gamma_concrete"]
    w_soil = plan_area * params["soil_height"] * params["gamma_soil"]
    pile_area = math_engine.calc_pile_area(params["pile_shape"], params["pile_dim"])
    w_pile = math_engine.calc_pile_weight(pile_area, params["pile_length"], params["gamma_pile"])

    # --- Coordinates & centroid ---
    x_coords = df_piles["X"].to_numpy(dtype=float)
    y_coords = df_piles["Y"].to_numpy(dtype=float)

    if params["centroid_mode"] == "Auto":
        x_c, y_c = math_engine.calc_centroid(x_coords, y_coords)
    else:
        x_c = params["x_centroid"]
        y_c = params["y_centroid"]

    x_rel, y_rel = math_engine.calc_relative_coords(x_coords, y_coords, x_c, y_c)
    sum_x_sq = float((x_rel ** 2).sum())
    sum_y_sq = float((y_rel ** 2).sum())
    i_polar = math_engine.calc_polar_inertia(x_rel, y_rel)

    n_piles = len(df_piles)
    pile_ids = df_piles["Pile_ID"].to_numpy()

    # --- Per load case (typically few); pile-level math is vectorized ---
    records = []
    for lc_row in df_lc.itertuples(index=False):
        fx_a, fy_a, fz_a, mx_a, my_a, mz_a = math_engine.convert_reactions_to_actions(
            lc_row.Fx, lc_row.Fy, lc_row.Fz, lc_row.Mx, lc_row.My, lc_row.Mz,
        )

        axial_arr = math_engine.calc_axial_forces(
            fz_act=fz_a, mx_act=mx_a, my_act=my_a, n_piles=n_piles,
            x_rel=x_rel, y_rel=y_rel, sum_x_sq=sum_x_sq, sum_y_sq=sum_y_sq,
            w_pilecap=w_pilecap, w_soil=w_soil, w_pile=w_pile,
        )
        hx_arr, hy_arr, h_res_arr = math_engine.calc_lateral_forces(
            fx_act=fx_a, fy_act=fy_a, mz_act=mz_a, n_piles=n_piles,
            x_rel=x_rel, y_rel=y_rel, i_polar=i_polar,
        )

        records.append(pd.DataFrame({
            "LC_ID": lc_row.LC_ID,
            "Pile_ID": pile_ids,
            "X": x_coords,
            "Y": y_coords,
            "Axial_Force": axial_arr,
            "Hx": hx_arr,
            "Hy": hy_arr,
            "H_Resultant": h_res_arr,
        }))

    return pd.concat(records, ignore_index=True)


def build_envelope(df_master: pd.DataFrame) -> pd.DataFrame:
    """Extract governing load cases per pile via groupby + idxmax/idxmin.

    Columns: [Pile_ID, X, Y, Max_Compression, LC_Max_Comp, Max_Tension,
    LC_Max_Tens, Max_Lateral, Max_Lat_Hx, Max_Lat_Hy, LC_Max_Lat,
    Min_Lateral, Min_Lat_Hx, Min_Lat_Hy, LC_Min_Lat].

    If a pile is never in compression (max axial < 0) the compression cell is
    forced to 0 with LC '-'; symmetrically for tension.
    """
    grouped = df_master.groupby("Pile_ID")

    # Max Compression = maximum (most positive) axial force
    idx_max_comp = grouped["Axial_Force"].idxmax()
    max_comp = df_master.loc[idx_max_comp, ["Pile_ID", "X", "Y", "Axial_Force", "LC_ID"]].rename(
        columns={"Axial_Force": "Max_Compression", "LC_ID": "LC_Max_Comp"},
    )
    mask_no_comp = max_comp["Max_Compression"] < 0
    max_comp.loc[mask_no_comp, ["Max_Compression", "LC_Max_Comp"]] = [0.0, "-"]

    # Max Tension = minimum (most negative) axial force
    idx_max_tens = grouped["Axial_Force"].idxmin()
    max_tens = df_master.loc[idx_max_tens, ["Pile_ID", "Axial_Force", "LC_ID"]].rename(
        columns={"Axial_Force": "Max_Tension", "LC_ID": "LC_Max_Tens"},
    )
    mask_no_tens = max_tens["Max_Tension"] > 0
    max_tens.loc[mask_no_tens, ["Max_Tension", "LC_Max_Tens"]] = [0.0, "-"]

    # Max / Min lateral resultant
    idx_max_lat = grouped["H_Resultant"].idxmax()
    max_lat = df_master.loc[idx_max_lat, ["Pile_ID", "H_Resultant", "Hx", "Hy", "LC_ID"]].rename(
        columns={"H_Resultant": "Max_Lateral", "Hx": "Max_Lat_Hx", "Hy": "Max_Lat_Hy", "LC_ID": "LC_Max_Lat"},
    )
    idx_min_lat = grouped["H_Resultant"].idxmin()
    min_lat = df_master.loc[idx_min_lat, ["Pile_ID", "H_Resultant", "Hx", "Hy", "LC_ID"]].rename(
        columns={"H_Resultant": "Min_Lateral", "Hx": "Min_Lat_Hx", "Hy": "Min_Lat_Hy", "LC_ID": "LC_Min_Lat"},
    )

    envelope = max_comp.merge(
        max_tens[["Pile_ID", "Max_Tension", "LC_Max_Tens"]], on="Pile_ID",
    ).merge(
        max_lat[["Pile_ID", "Max_Lateral", "Max_Lat_Hx", "Max_Lat_Hy", "LC_Max_Lat"]], on="Pile_ID",
    ).merge(
        min_lat[["Pile_ID", "Min_Lateral", "Min_Lat_Hx", "Min_Lat_Hy", "LC_Min_Lat"]], on="Pile_ID",
    )

    return envelope.reset_index(drop=True)
