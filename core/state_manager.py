"""
Session state management for save/load project as JSON.
"""

import json
from datetime import datetime

import pandas as pd


def export_state(
    params: dict,
    df_piles: pd.DataFrame,
    df_lc: pd.DataFrame,
) -> str:
    """Serialize all input parameters and table data to a JSON string.

    Parameters
    ----------
    params : dict of all UI parameters (pilecap dims, soil, pile, centroid, unit)
    df_piles : DataFrame with columns [Pile_ID, X, Y]
    df_lc : DataFrame with columns [LC_ID, Fx, Fy, Fz, Mx, My, Mz]

    Returns
    -------
    JSON string ready for download.
    """
    state_dict = {
        "version": "0.0",
        "saved_at": datetime.now().isoformat(),
        "parameters": params,
        "pile_coordinates": df_piles.to_dict(orient="records"),
        "load_cases": df_lc.to_dict(orient="records"),
    }
    return json.dumps(state_dict, indent=2, ensure_ascii=False)


def import_state(json_bytes: bytes) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Deserialize JSON project file into parameters and DataFrames.

    Parameters
    ----------
    json_bytes : raw bytes from uploaded file

    Returns
    -------
    Tuple of (params_dict, df_piles, df_lc)

    Raises
    ------
    ValueError : if the JSON is corrupted or missing required keys.
    """
    try:
        state_dict = json.loads(json_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"File JSON tidak valid: {exc}") from exc

    required_keys = ["parameters", "pile_coordinates", "load_cases"]
    missing_keys = [k for k in required_keys if k not in state_dict]
    if missing_keys:
        raise ValueError(f"Key yang hilang dalam file JSON: {missing_keys}")

    params = state_dict["parameters"]

    try:
        df_piles = pd.DataFrame(state_dict["pile_coordinates"])
        df_lc = pd.DataFrame(state_dict["load_cases"])
    except Exception as exc:
        raise ValueError(f"Gagal membaca data tabel dari JSON: {exc}") from exc

    # Validate required columns
    pile_cols = {"Pile_ID", "X", "Y"}
    lc_cols = {"LC_ID", "Fx", "Fy", "Fz", "Mx", "My", "Mz"}

    if not pile_cols.issubset(set(df_piles.columns)):
        raise ValueError(f"Kolom pile coordinates tidak lengkap. Dibutuhkan: {pile_cols}")
    if not lc_cols.issubset(set(df_lc.columns)):
        raise ValueError(f"Kolom load cases tidak lengkap. Dibutuhkan: {lc_cols}")

    return params, df_piles, df_lc
