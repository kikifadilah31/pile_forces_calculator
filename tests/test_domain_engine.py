"""Tests for domain orchestration: master output cross-join and envelope."""

import numpy as np
import pandas as pd

from pile_forces import config, domain_engine

PILES = pd.DataFrame({"Pile_ID": ["P1", "P2", "P3", "P4"], "X": [0.0, 3.0, 0.0, 3.0], "Y": [0.0, 0.0, 3.0, 3.0]})
LC = pd.DataFrame({
    "LC_ID": ["LC1", "LC2"],
    "Fx": [100.0, -80.0], "Fy": [50.0, 120.0], "Fz": [1000.0, 1400.0],
    "Mx": [200.0, -260.0], "My": [150.0, 90.0], "Mz": [80.0, -60.0],
})
PARAMS = dict(config.DEFAULT_PARAMS)


def test_master_output_is_full_cross_join():
    m = domain_engine.build_master_output(PILES, LC, PARAMS)
    assert len(m) == len(PILES) * len(LC)
    assert list(m.columns) == config.MASTER_COLUMNS


def test_envelope_one_row_per_pile():
    m = domain_engine.build_master_output(PILES, LC, PARAMS)
    e = domain_engine.build_envelope(m)
    assert len(e) == len(PILES)
    assert set(["Max_Compression", "LC_Max_Comp", "Max_Tension", "Max_Lateral"]).issubset(e.columns)


def test_envelope_matches_manual_groupby():
    m = domain_engine.build_master_output(PILES, LC, PARAMS)
    e = domain_engine.build_envelope(m).set_index("Pile_ID")
    for pid, grp in m.groupby("Pile_ID"):
        assert np.isclose(e.loc[pid, "Max_Compression"], grp["Axial_Force"].max(), rtol=config.VALIDATION_RTOL)
        assert np.isclose(e.loc[pid, "Max_Lateral"], grp["H_Resultant"].max(), rtol=config.VALIDATION_RTOL)


def test_envelope_no_tension_forced_to_zero():
    """A heavy-compression-only case: every pile stays in compression -> tension cell = 0."""
    heavy = pd.DataFrame({
        "LC_ID": ["LC1"], "Fx": [0.0], "Fy": [0.0], "Fz": [5000.0],
        "Mx": [0.0], "My": [0.0], "Mz": [0.0],
    })
    m = domain_engine.build_master_output(PILES, heavy, PARAMS)
    e = domain_engine.build_envelope(m)
    assert (e["Max_Tension"] == 0.0).all()
    assert (e["LC_Max_Tens"] == "-").all()
