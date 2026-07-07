"""Fail-fast validation tests: corrupt input MUST raise (Core 3)."""

import pandas as pd
import pytest

from pile_forces import config, validators


def _good_piles():
    return pd.DataFrame({"Pile_ID": ["P1", "P2"], "X": [0.0, 1.0], "Y": [0.0, 1.0]})


def _good_lc():
    return pd.DataFrame({
        "LC_ID": ["LC1"], "Fx": [1.0], "Fy": [1.0], "Fz": [1.0],
        "Mx": [1.0], "My": [1.0], "Mz": [1.0],
    })


def test_valid_piles_pass():
    out = validators.validate_piles_df(_good_piles())
    assert list(out.columns) == config.PILE_COLUMNS or set(config.PILE_COLUMNS).issubset(out.columns)


def test_missing_pile_column_raises():
    df = _good_piles().drop(columns=["Y"])
    with pytest.raises(ValueError, match="kolom hilang"):
        validators.validate_piles_df(df)


def test_empty_piles_raises():
    with pytest.raises(ValueError, match="kosong"):
        validators.validate_piles_df(_good_piles().iloc[0:0])


def test_duplicate_pile_id_raises():
    df = _good_piles()
    df.loc[1, "Pile_ID"] = "P1"
    with pytest.raises(ValueError, match="duplikat"):
        validators.validate_piles_df(df)


def test_non_numeric_coord_raises():
    # X column carries a non-numeric string (as it would from a raw CSV/data editor).
    df = pd.DataFrame({"Pile_ID": ["P1", "P2"], "X": ["abc", "1.0"], "Y": ["0.0", "1.0"]})
    with pytest.raises(ValueError, match="non-numerik"):
        validators.validate_piles_df(df)


def test_duplicate_lc_id_raises():
    df = pd.concat([_good_lc(), _good_lc()], ignore_index=True)
    with pytest.raises(ValueError, match="duplikat"):
        validators.validate_load_cases_df(df)


def test_params_negative_dimension_raises():
    params = dict(config.DEFAULT_PARAMS)
    params["pilecap_length"] = -1.0
    with pytest.raises(ValueError, match="> 0"):
        validators.validate_params(params)


def test_params_bad_shape_raises():
    params = dict(config.DEFAULT_PARAMS)
    params["pile_shape"] = "Hexagon"
    with pytest.raises(ValueError, match="pile_shape"):
        validators.validate_params(params)


def test_params_defaults_valid():
    assert validators.validate_params(dict(config.DEFAULT_PARAMS)) is not None


def test_pilecap_polygon_valid():
    df = pd.DataFrame({"X": [0.0, 2.0, 2.0, 0.0], "Y": [0.0, 0.0, 2.0, 2.0]})
    out = validators.validate_pilecap_df(df)
    assert len(out) == 4


def test_pilecap_polygon_too_few_points_raises():
    df = pd.DataFrame({"X": [0.0, 2.0], "Y": [0.0, 0.0]})
    with pytest.raises(ValueError, match="minimal 3"):
        validators.validate_pilecap_df(df)


def test_pilecap_polygon_missing_column_raises():
    df = pd.DataFrame({"X": [0.0, 2.0, 1.0]})
    with pytest.raises(ValueError, match="kolom hilang"):
        validators.validate_pilecap_df(df)
