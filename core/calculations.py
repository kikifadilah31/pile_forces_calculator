"""
Core engineering calculations for pile force distribution.

All internal calculations use kN and meters.
No Streamlit imports — pure math functions using pandas and numpy.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Step 1: Self-Weight Calculations
# ---------------------------------------------------------------------------

def calc_pilecap_weight(length: float, width: float, height: float, gamma_concrete: float) -> float:
    """Calculate pilecap self-weight (kN).

    W_pc = Length × Width × Height × γ_concrete
    """
    return length * width * height * gamma_concrete


def calc_soil_weight(length: float, width: float, height_soil: float, gamma_soil: float) -> float:
    """Calculate soil backfill weight on pilecap (kN).

    W_soil = Length × Width × H_soil × γ_soil
    # TODO: subtract pier area from soil weight in future update (currently conservative)
    """
    return length * width * height_soil * gamma_soil


def calc_pile_area(shape: str, dimension: float) -> float:
    """Calculate single pile cross-sectional area (m²).

    Square: B²
    Circle: 0.25 × π × D²
    """
    if shape == "Square":
        return dimension ** 2
    elif shape == "Circle":
        return 0.25 * np.pi * dimension ** 2
    else:
        raise ValueError(f"Unknown pile shape: {shape}. Use 'Square' or 'Circle'.")


def calc_pile_weight(area: float, length_pile: float, gamma_pile: float) -> float:
    """Calculate single pile self-weight (kN).

    W_pile = A_pile × L_pile × γ_pile
    """
    return area * length_pile * gamma_pile


# ---------------------------------------------------------------------------
# Step 2: Reaction to Action Conversion
# ---------------------------------------------------------------------------

def convert_reactions_to_actions(df_lc: pd.DataFrame) -> pd.DataFrame:
    """Convert Midas reaction forces to foundation action forces.

    Fx_act = -Fx, Fy_act = -Fy, Fz_act = +Fz (kept positive for compression),
    Mx_act = -Mx, My_act = -My, Mz_act = -Mz
    """
    df_act = df_lc.copy()
    df_act["Fx"] = -df_lc["Fx"]
    df_act["Fy"] = -df_lc["Fy"]
    # Fz remains positive (gravity downward, Midas reaction +Fz = upward,
    # foundation design: downward compression is positive)
    df_act["Fz"] = df_lc["Fz"]
    df_act["Mx"] = -df_lc["Mx"]
    df_act["My"] = -df_lc["My"]
    df_act["Mz"] = -df_lc["Mz"]
    return df_act


# ---------------------------------------------------------------------------
# Step 3: Centroid & Relative Coordinates
# ---------------------------------------------------------------------------

def calc_centroid(df_piles: pd.DataFrame) -> tuple[float, float]:
    """Calculate pile group centroid as mean of coordinates."""
    x_c = df_piles["X"].mean()
    y_c = df_piles["Y"].mean()
    return x_c, y_c


def calc_relative_coords(df_piles: pd.DataFrame, x_c: float, y_c: float) -> pd.DataFrame:
    """Calculate relative coordinates for each pile from centroid.

    x_i = X_global,i - X_c
    y_i = Y_global,i - Y_c
    """
    df_rel = df_piles.copy()
    df_rel["x_rel"] = df_rel["X"] - x_c
    df_rel["y_rel"] = df_rel["Y"] - y_c
    return df_rel


def calc_polar_inertia(x_rel: pd.Series, y_rel: pd.Series) -> float:
    """Calculate group polar moment of inertia.

    I_polar = Σ(x_i²) + Σ(y_i²)
    """
    return (x_rel ** 2).sum() + (y_rel ** 2).sum()


# ---------------------------------------------------------------------------
# Step 4 & 5: Force Distribution (Vectorized)
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
) -> np.ndarray:
    """Calculate axial force distribution for each pile (vectorized).

    P_axial,i = P_total/n - Mx_act·y_i/Σ(y²) + My_act·x_i/Σ(x²) + W_pile

    Zero-division protection applied when Σx² or Σy² is zero.
    """
    p_total = fz_act + w_pilecap + w_soil
    axial_base = p_total / n_piles

    # Moment contribution around X-axis (bending about X → distributes via y)
    mx_contrib = np.where(
        sum_y_sq > 1e-12,
        -(mx_act * y_rel) / sum_y_sq,
        0.0,
    )

    # Moment contribution around Y-axis (bending about Y → distributes via x)
    my_contrib = np.where(
        sum_x_sq > 1e-12,
        (my_act * x_rel) / sum_x_sq,
        0.0,
    )

    return axial_base + mx_contrib + my_contrib + w_pile


def calc_lateral_forces(
    fx_act: float,
    fy_act: float,
    mz_act: float,
    n_piles: int,
    x_rel: np.ndarray,
    y_rel: np.ndarray,
    i_polar: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate lateral force distribution including torsion (vectorized).

    Hx_i = Fx_act/n - Mz_act·y_i / I_polar
    Hy_i = Fy_act/n + Mz_act·x_i / I_polar
    H_resultant = √(Hx² + Hy²)

    Returns (Hx, Hy, H_resultant) arrays.
    """
    hx_base = fx_act / n_piles
    hy_base = fy_act / n_piles

    # Torsion contribution
    mz_contrib_x = np.where(
        i_polar > 1e-12,
        -(mz_act * y_rel) / i_polar,
        0.0,
    )
    mz_contrib_y = np.where(
        i_polar > 1e-12,
        (mz_act * x_rel) / i_polar,
        0.0,
    )

    hx_arr = hx_base + mz_contrib_x
    hy_arr = hy_base + mz_contrib_y
    h_resultant = np.sqrt(hx_arr ** 2 + hy_arr ** 2)

    return hx_arr, hy_arr, h_resultant


# ---------------------------------------------------------------------------
# Master Output Builder
# ---------------------------------------------------------------------------

def build_master_output(
    df_piles: pd.DataFrame,
    df_lc: pd.DataFrame,
    params: dict,
) -> pd.DataFrame:
    """Build master output DataFrame by cross-joining Load Cases × Piles.

    Parameters
    ----------
    df_piles : DataFrame with columns [Pile_ID, X, Y]
    df_lc : DataFrame with columns [LC_ID, Fx, Fy, Fz, Mx, My, Mz] (raw reactions)
    params : dict with keys:
        pilecap_length, pilecap_width, pilecap_height, gamma_concrete,
        soil_height, gamma_soil,
        pile_shape, pile_dim, pile_length, gamma_pile,
        centroid_mode, x_centroid, y_centroid

    Returns
    -------
    DataFrame with columns [LC_ID, Pile_ID, X, Y, Axial_Force, Hx, Hy, H_Resultant]
    """
    # --- Self-weights ---
    w_pilecap = calc_pilecap_weight(
        params["pilecap_length"], params["pilecap_width"],
        params["pilecap_height"], params["gamma_concrete"],
    )
    w_soil = calc_soil_weight(
        params["pilecap_length"], params["pilecap_width"],
        params["soil_height"], params["gamma_soil"],
    )
    pile_area = calc_pile_area(params["pile_shape"], params["pile_dim"])
    w_pile = calc_pile_weight(pile_area, params["pile_length"], params["gamma_pile"])

    # --- Centroid ---
    if params["centroid_mode"] == "Auto":
        x_c, y_c = calc_centroid(df_piles)
    else:
        x_c = params["x_centroid"]
        y_c = params["y_centroid"]

    # --- Relative coordinates ---
    df_piles_rel = calc_relative_coords(df_piles, x_c, y_c)
    x_rel_arr = df_piles_rel["x_rel"].values
    y_rel_arr = df_piles_rel["y_rel"].values

    sum_x_sq = (x_rel_arr ** 2).sum()
    sum_y_sq = (y_rel_arr ** 2).sum()
    i_polar = calc_polar_inertia(
        df_piles_rel["x_rel"], df_piles_rel["y_rel"],
    )

    n_piles = len(df_piles)

    # --- Convert reactions to actions ---
    df_lc_act = convert_reactions_to_actions(df_lc)

    # --- Vectorized cross-join and calculation ---
    records = []
    for _, lc_row in df_lc_act.iterrows():
        # NOTE: iterrows used here over load cases (typically <100 rows),
        # while pile-level math is fully vectorized via numpy arrays.
        lc_id = lc_row["LC_ID"]

        axial_arr = calc_axial_forces(
            fz_act=lc_row["Fz"],
            mx_act=lc_row["Mx"],
            my_act=lc_row["My"],
            n_piles=n_piles,
            x_rel=x_rel_arr,
            y_rel=y_rel_arr,
            sum_x_sq=sum_x_sq,
            sum_y_sq=sum_y_sq,
            w_pilecap=w_pilecap,
            w_soil=w_soil,
            w_pile=w_pile,
        )

        hx_arr, hy_arr, h_res_arr = calc_lateral_forces(
            fx_act=lc_row["Fx"],
            fy_act=lc_row["Fy"],
            mz_act=lc_row["Mz"],
            n_piles=n_piles,
            x_rel=x_rel_arr,
            y_rel=y_rel_arr,
            i_polar=i_polar,
        )

        lc_df = pd.DataFrame({
            "LC_ID": lc_id,
            "Pile_ID": df_piles_rel["Pile_ID"].values,
            "X": df_piles_rel["X"].values,
            "Y": df_piles_rel["Y"].values,
            "Axial_Force": axial_arr,
            "Hx": hx_arr,
            "Hy": hy_arr,
            "H_Resultant": h_res_arr,
        })
        records.append(lc_df)

    df_master = pd.concat(records, ignore_index=True)
    return df_master


# ---------------------------------------------------------------------------
# Envelope (Governing Load Case) Extractor
# ---------------------------------------------------------------------------

def build_envelope(df_master: pd.DataFrame) -> pd.DataFrame:
    """Extract governing load cases per pile using groupby + idxmax/idxmin.

    Returns DataFrame with columns:
    [Pile_ID, Max_Compression, LC_Max_Comp, Max_Tension, LC_Max_Tens, Max_Lateral, LC_Max_Lat]
    """
    grouped = df_master.groupby("Pile_ID")

    # Max Compression = maximum positive Axial_Force
    idx_max_comp = grouped["Axial_Force"].idxmax()
    max_comp = df_master.loc[idx_max_comp, ["Pile_ID", "X", "Y", "Axial_Force", "LC_ID"]].rename(
        columns={"Axial_Force": "Max_Compression", "LC_ID": "LC_Max_Comp"},
    )

    # Max Tension = minimum Axial_Force (most negative)
    idx_max_tens = grouped["Axial_Force"].idxmin()
    max_tens = df_master.loc[idx_max_tens, ["Pile_ID", "Axial_Force", "LC_ID"]].rename(
        columns={"Axial_Force": "Max_Tension", "LC_ID": "LC_Max_Tens"},
    )

    # Max Lateral = maximum H_Resultant
    idx_max_lat = grouped["H_Resultant"].idxmax()
    max_lat = df_master.loc[idx_max_lat, ["Pile_ID", "H_Resultant", "Hx", "Hy", "LC_ID"]].rename(
        columns={"H_Resultant": "Max_Lateral", "Hx": "Max_Lat_Hx", "Hy": "Max_Lat_Hy", "LC_ID": "LC_Max_Lat"},
    )

    # Min Lateral = minimum H_Resultant
    idx_min_lat = grouped["H_Resultant"].idxmin()
    min_lat = df_master.loc[idx_min_lat, ["Pile_ID", "H_Resultant", "Hx", "Hy", "LC_ID"]].rename(
        columns={"H_Resultant": "Min_Lateral", "Hx": "Min_Lat_Hx", "Hy": "Min_Lat_Hy", "LC_ID": "LC_Min_Lat"},
    )

    # Merge all envelopes
    envelope = max_comp.merge(
        max_tens[["Pile_ID", "Max_Tension", "LC_Max_Tens"]], on="Pile_ID",
    ).merge(
        max_lat[["Pile_ID", "Max_Lateral", "Max_Lat_Hx", "Max_Lat_Hy", "LC_Max_Lat"]], on="Pile_ID",
    ).merge(
        min_lat[["Pile_ID", "Min_Lateral", "Min_Lat_Hx", "Min_Lat_Hy", "LC_Min_Lat"]], on="Pile_ID",
    )

    return envelope.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Unit Conversion
# ---------------------------------------------------------------------------

def convert_units(df: pd.DataFrame, unit: str) -> pd.DataFrame:
    """Convert force columns between kN and Ton.

    1 Ton = 9.81 kN → to convert kN to Ton, divide by 9.81.
    Internal calculations are always in kN.
    """
    force_cols = ["Axial_Force", "Hx", "Hy", "H_Resultant"]
    # Filter to only existing columns
    existing_force_cols = [col for col in force_cols if col in df.columns]

    # Also handle envelope columns
    envelope_cols = [
        "Max_Compression", "Max_Tension", 
        "Max_Lateral", "Max_Lat_Hx", "Max_Lat_Hy",
        "Min_Lateral", "Min_Lat_Hx", "Min_Lat_Hy"
    ]
    existing_envelope_cols = [col for col in envelope_cols if col in df.columns]

    all_cols = existing_force_cols + existing_envelope_cols

    df_out = df.copy()
    if unit == "Ton" and len(all_cols) > 0:
        df_out[all_cols] = df_out[all_cols] / 9.81

    return df_out
