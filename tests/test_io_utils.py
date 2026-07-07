"""Tests for the I/O boundary: unit conversion, layered params merge, loading."""

import json

import numpy as np
import pandas as pd
import pytest

from pile_forces import config, io_utils


def test_convert_units_kn_is_identity():
    df = pd.DataFrame({"Axial_Force": [981.0], "Hx": [9.81], "Hy": [0.0], "H_Resultant": [9.81]})
    out = io_utils.convert_units(df, "kN")
    pd.testing.assert_frame_equal(out, df)


def test_convert_units_kn_to_ton():
    df = pd.DataFrame({"Axial_Force": [981.0], "Hx": [9.81], "Hy": [0.0], "H_Resultant": [9.81]})
    out = io_utils.convert_units(df, "Ton")
    assert np.isclose(out["Axial_Force"].iloc[0], 100.0, rtol=config.VALIDATION_RTOL)
    assert np.isclose(out["Hx"].iloc[0], 1.0, rtol=config.VALIDATION_RTOL)


def test_convert_units_ignores_non_force_columns():
    df = pd.DataFrame({"X": [1.0], "Y": [2.0], "Axial_Force": [9.81]})
    out = io_utils.convert_units(df, "Ton")
    assert out["X"].iloc[0] == 1.0 and out["Y"].iloc[0] == 2.0


def test_load_params_defaults_when_none():
    params = io_utils.load_params(None, None)
    assert params == config.DEFAULT_PARAMS
    assert params is not config.DEFAULT_PARAMS  # a copy, not the shared dict


def test_load_params_layered_merge(tmp_path):
    pfile = tmp_path / "p.json"
    pfile.write_text(json.dumps({"pile_shape": "Square", "pile_dim": 0.5}))
    # File overrides default; CLI override wins over file; None is ignored.
    params = io_utils.load_params(str(pfile), {"pile_dim": 0.8, "gamma_pile": None})
    assert params["pile_shape"] == "Square"     # from file
    assert params["pile_dim"] == 0.8            # CLI override beats file
    assert params["gamma_pile"] == config.DEFAULT_PARAMS["gamma_pile"]  # None ignored


def test_load_params_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        io_utils.load_params("does_not_exist.json", None)


def test_load_piles_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        io_utils.load_piles_csv("nope.csv")


def test_load_piles_reorders_columns(tmp_path):
    csv = tmp_path / "piles.csv"
    csv.write_text("Y,X,Pile_ID\n0,1,P1\n")
    df = io_utils.load_piles_csv(str(csv))
    assert list(df.columns) == config.PILE_COLUMNS


def test_read_table_excel_dispatch(tmp_path):
    # Excel input is read via extension dispatch and validated like CSV
    xlsx = tmp_path / "piles.xlsx"
    pd.DataFrame({"Pile_ID": ["P1", "P2"], "X": [0.0, 3.0], "Y": [0.0, 0.0]}).to_excel(xlsx, index=False)
    df = io_utils.load_piles_csv(str(xlsx))
    assert list(df.columns) == config.PILE_COLUMNS
    assert len(df) == 2


def test_write_results_xlsx_roundtrip(tmp_path):
    master = pd.DataFrame({"LC_ID": ["LC1"], "Pile_ID": ["P1"], "Axial_Force": [123.45]})
    envelope = pd.DataFrame({"Pile_ID": ["P1"], "Max_Compression": [123.45]})
    out = tmp_path / "results.xlsx"
    io_utils.write_results_xlsx(str(out), master, envelope)
    assert out.exists()
    back = pd.read_excel(out, sheet_name="Master")
    assert np.isclose(back["Axial_Force"].iloc[0], 123.45, rtol=config.VALIDATION_RTOL)
    assert "Envelope" in pd.ExcelFile(out).sheet_names
