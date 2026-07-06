"""
I/O boundary utilities: CSV loading, params resolution, unit conversion.

This is the ONLY place unit conversion happens (template Core 2). Input CSV
is assumed to already be in the internal system (kN, m — Midas export), so
no input conversion is required; the kN->Ton conversion is applied only when
producing display/output tables.

No auto-detection: input file paths are always passed explicitly (by the
CLI or the caller). Missing files raise immediately (fail-fast).
"""

import json
import os

import pandas as pd

from . import config

# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def _read_csv(path: str, name: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"[{name}] file tidak ditemukan: {path}")
    try:
        return pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001 — surface a clean diagnostic
        raise ValueError(f"[{name}] gagal membaca CSV {path}: {exc}") from exc


def load_piles_csv(path: str) -> pd.DataFrame:
    """Load pile coordinates CSV. Returns columns in config.PILE_COLUMNS order.

    Coordinates are in meters. Required columns: Pile_ID, X, Y.
    """
    df = _read_csv(path, "pile coordinates")
    missing = set(config.PILE_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"[pile coordinates] kolom hilang: {sorted(missing)}. "
            f"Ditemukan: {list(df.columns)}"
        )
    return df[config.PILE_COLUMNS].copy()


def load_load_cases_csv(path: str) -> pd.DataFrame:
    """Load load cases CSV. Returns columns in config.LC_COLUMNS order.

    Forces in kN, moments in kN·m. Required columns:
    LC_ID, Fx, Fy, Fz, Mx, My, Mz.
    """
    df = _read_csv(path, "load cases")
    missing = set(config.LC_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"[load cases] kolom hilang: {sorted(missing)}. "
            f"Ditemukan: {list(df.columns)}"
        )
    return df[config.LC_COLUMNS].copy()


# ---------------------------------------------------------------------------
# Params resolution (layered merge — Core 6)
# ---------------------------------------------------------------------------

def load_params(params_path: str | None = None, overrides: dict | None = None) -> dict:
    """Resolve design parameters via a layered merge.

    Precedence (lowest -> highest):
        config.DEFAULT_PARAMS  ->  params.json (if given)  ->  CLI overrides

    Parameters
    ----------
    params_path : path to a JSON params file, or None to skip that layer.
    overrides : dict of explicit values (e.g. parsed CLI flags). Keys whose
        value is None are ignored so unset flags do not clobber lower layers.

    Raises
    ------
    FileNotFoundError / ValueError on a missing or malformed params file.
    """
    merged = dict(config.DEFAULT_PARAMS)

    if params_path is not None:
        if not os.path.isfile(params_path):
            raise FileNotFoundError(f"[params] file tidak ditemukan: {params_path}")
        try:
            with open(params_path, encoding="utf-8") as fh:
                file_params = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"[params] JSON tidak valid ({params_path}): {exc}") from exc
        if not isinstance(file_params, dict):
            raise ValueError(f"[params] isi JSON harus objek/dict, bukan {type(file_params).__name__}.")
        # Allow either a flat dict or one nested under "parameters"
        if "parameters" in file_params and isinstance(file_params["parameters"], dict):
            file_params = file_params["parameters"]
        merged.update({k: v for k, v in file_params.items() if k in config.DEFAULT_PARAMS})

    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None and k in config.DEFAULT_PARAMS})

    return merged


# ---------------------------------------------------------------------------
# Unit conversion (output boundary only)
# ---------------------------------------------------------------------------

def convert_units(df: pd.DataFrame, unit: str) -> pd.DataFrame:
    """Convert force columns from internal kN to the requested output unit.

    1 Ton = 9.81 kN, so kN -> Ton divides by config.TON_TO_KN. Non-force
    columns (coordinates, IDs) are untouched. Returns a copy.
    """
    all_force_cols = config.MASTER_FORCE_COLUMNS + config.ENVELOPE_FORCE_COLUMNS
    cols = [c for c in all_force_cols if c in df.columns]

    df_out = df.copy()
    if unit == "Ton" and cols:
        df_out[cols] = df_out[cols] / config.TON_TO_KN
    return df_out
