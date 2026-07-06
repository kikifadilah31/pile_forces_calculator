"""
End-to-end CLI integration + golden-file regression (Core 1, Core 8).

Runs the full pipeline on the committed sample inputs into a temp output dir,
asserts every expected artifact exists and run_manifest.json is populated, and
compares the numeric tables against locked golden files with rtol.
"""

import json
import os

import numpy as np
import pandas as pd
import pytest

from pile_forces import __version__, config
from pile_forces.cli import main

# V&V uses dedicated, locked fixtures under tests/data — NOT the user-editable
# input/ samples — so editing real project data never breaks the golden tests.
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(TESTS_DIR, "golden")
DATA = os.path.join(TESTS_DIR, "data")
PILES = os.path.join(DATA, "piles.csv")
LC = os.path.join(DATA, "load_cases.csv")
PARAMS = os.path.join(DATA, "params.json")
N_LOAD_CASES = 3  # fixtures contain LC1..LC3


def _latest_run(parent: str) -> str:
    runs = [os.path.join(parent, d) for d in os.listdir(parent) if d.startswith(config.OUTPUT_PREFIX)]
    return max(runs, key=os.path.getmtime)


@pytest.fixture()
def run_dir(tmp_path):
    rc = main([
        "--piles", PILES, "--load-cases", LC, "--params", PARAMS,
        "--output", str(tmp_path), "--no-report",  # skip PDF to keep the test fast/offline
    ])
    assert rc == 0
    return _latest_run(str(tmp_path))


def test_expected_artifacts_exist(run_dir):
    for rel in ["run_manifest.json", "run.log", "master_output.csv", "envelope.csv", "SUMMARY.md"]:
        assert os.path.isfile(os.path.join(run_dir, rel)), f"missing {rel}"
    plots = os.listdir(os.path.join(run_dir, "plots"))
    # 2 plots per LC + 4 envelope plots
    assert len(plots) == N_LOAD_CASES * 2 + 4


def test_manifest_is_populated(run_dir):
    with open(os.path.join(run_dir, "run_manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["tool_version"] == __version__
    assert manifest["inputs"], "input hashes should be recorded"
    assert all(len(h) == 64 for h in manifest["inputs"].values())  # sha256 hex
    assert manifest["parameters"]["pile_shape"] in config.VALID_PILE_SHAPES


def test_master_output_matches_golden(run_dir):
    got = pd.read_csv(os.path.join(run_dir, "master_output.csv"))
    exp = pd.read_csv(os.path.join(GOLDEN, "master_output.csv"))
    assert list(got.columns) == list(exp.columns)
    for col in config.MASTER_FORCE_COLUMNS:
        assert np.allclose(got[col], exp[col], rtol=config.VALIDATION_RTOL), f"mismatch in {col}"


def test_envelope_matches_golden(run_dir):
    got = pd.read_csv(os.path.join(run_dir, "envelope.csv"))
    exp = pd.read_csv(os.path.join(GOLDEN, "envelope.csv"))
    assert list(got.columns) == list(exp.columns)
    for col in config.ENVELOPE_FORCE_COLUMNS:
        if col in exp.columns:
            assert np.allclose(got[col], exp[col], rtol=config.VALIDATION_RTOL), f"mismatch in {col}"
