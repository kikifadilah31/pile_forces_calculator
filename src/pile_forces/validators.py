"""
Fail-fast input validation (template Core 3).

Every failure here RAISES with a diagnostic message — corrupt or ambiguous
input must stop the run loudly, never silently become NaN. This layer is
distinct from "design failure" (which the elastic distribution never produces).
"""

import pandas as pd

from . import config


def _coerce_numeric(df: pd.DataFrame, columns: list[str], name: str) -> pd.DataFrame:
    """Coerce given columns to numeric; raise if any value is non-numeric/NaN."""
    df = df.copy()
    for col in columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        bad = coerced.isna()
        if bad.any():
            rows = (df.index[bad] + 1).tolist()  # 1-based for human diagnostics
            raise ValueError(
                f"[{name}] kolom '{col}' berisi nilai non-numerik/kosong pada baris {rows}."
            )
        df[col] = coerced
    return df


def validate_piles_df(df: pd.DataFrame) -> pd.DataFrame:
    """Validate pile coordinates. Returns a cleaned, numeric-typed copy."""
    name = "pile coordinates"
    missing = set(config.PILE_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"[{name}] kolom hilang: {sorted(missing)}. Ditemukan: {list(df.columns)}")
    if df.empty:
        raise ValueError(f"[{name}] tabel kosong — minimal 1 pile diperlukan.")

    if df["Pile_ID"].isna().any():
        raise ValueError(f"[{name}] terdapat Pile_ID kosong.")
    dupes = df["Pile_ID"].astype(str)[df["Pile_ID"].astype(str).duplicated()].unique().tolist()
    if dupes:
        raise ValueError(f"[{name}] Pile_ID duplikat: {dupes}. Setiap pile harus unik.")

    return _coerce_numeric(df, config.PILE_NUMERIC_COLUMNS, name)


def validate_pilecap_df(df: pd.DataFrame) -> pd.DataFrame:
    """Validate custom pilecap polygon vertices. Returns a numeric-typed copy.

    Requires columns X, Y, at least 3 vertices, and no non-numeric/blank cells.
    """
    name = "pilecap polygon"
    missing = set(config.PILECAP_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"[{name}] kolom hilang: {sorted(missing)}. Ditemukan: {list(df.columns)}")
    if len(df) < 3:
        raise ValueError(f"[{name}] minimal 3 titik diperlukan untuk membentuk polygon (diberikan: {len(df)}).")
    return _coerce_numeric(df, config.PILECAP_COLUMNS, name)


def validate_load_cases_df(df: pd.DataFrame) -> pd.DataFrame:
    """Validate load cases. Returns a cleaned, numeric-typed copy."""
    name = "load cases"
    missing = set(config.LC_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"[{name}] kolom hilang: {sorted(missing)}. Ditemukan: {list(df.columns)}")
    if df.empty:
        raise ValueError(f"[{name}] tabel kosong — minimal 1 load case diperlukan.")

    if df["LC_ID"].isna().any():
        raise ValueError(f"[{name}] terdapat LC_ID kosong.")
    dupes = df["LC_ID"].astype(str)[df["LC_ID"].astype(str).duplicated()].unique().tolist()
    if dupes:
        raise ValueError(f"[{name}] LC_ID duplikat: {dupes}. Setiap load case harus unik.")

    return _coerce_numeric(df, config.LC_NUMERIC_COLUMNS, name)


def validate_params(params: dict) -> dict:
    """Validate resolved design parameters. Returns the params unchanged."""
    name = "params"

    positive_keys = [
        "pilecap_length", "pilecap_width", "pilecap_height", "gamma_concrete",
        "gamma_soil", "pile_dim", "pile_length", "gamma_pile",
    ]
    for key in positive_keys:
        val = params.get(key)
        if val is None or float(val) <= 0:
            raise ValueError(f"[{name}] '{key}' harus > 0 (diberikan: {val!r}).")

    if float(params.get("soil_height", 0)) < 0:
        raise ValueError(f"[{name}] 'soil_height' tidak boleh negatif (diberikan: {params.get('soil_height')!r}).")

    shape = params.get("pile_shape")
    if shape not in config.VALID_PILE_SHAPES:
        raise ValueError(f"[{name}] 'pile_shape' harus salah satu dari {config.VALID_PILE_SHAPES} (diberikan: {shape!r}).")

    mode = params.get("centroid_mode")
    if mode not in config.VALID_CENTROID_MODES:
        raise ValueError(f"[{name}] 'centroid_mode' harus salah satu dari {config.VALID_CENTROID_MODES} (diberikan: {mode!r}).")

    unit = params.get("output_unit")
    if unit not in config.VALID_OUTPUT_UNITS:
        raise ValueError(f"[{name}] 'output_unit' harus salah satu dari {config.VALID_OUTPUT_UNITS} (diberikan: {unit!r}).")

    # Capacity check: at least one capacity must be > 0 when enabled, and no
    # negative capacities allowed (fail-fast on a misconfigured check).
    if params.get("check_capacity"):
        caps = {k: float(params.get(k, 0) or 0) for k in ("cap_axial_comp", "cap_axial_tension", "cap_lateral")}
        if any(v < 0 for v in caps.values()):
            raise ValueError(f"[{name}] kapasitas tidak boleh negatif (diberikan: {caps}).")
        if all(v <= 0 for v in caps.values()):
            raise ValueError(
                f"[{name}] 'check_capacity' aktif tapi semua kapasitas 0 — "
                "isi minimal satu dari cap_axial_comp / cap_axial_tension / cap_lateral (> 0)."
            )

    return params
