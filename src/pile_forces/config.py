"""
Centralized configuration — single source of truth (template Core 6).

No magic numbers elsewhere: any constant used more than once lives here.
CLI flags and params files may override the design defaults, but the
defaults themselves are defined only in this module.
"""

# ---------------------------------------------------------------------------
# Units Policy (Core 2)
# ---------------------------------------------------------------------------
# Internal unit system is kN and meters (moments in kN·m). This matches the
# original engine so numerical results stay identical (no regression).
# Conversion to Ton happens ONLY at the output boundary (io_utils.convert_units).
UNIT_SYSTEM = "kN-m"          # internal: kN, m, kN·m
TON_TO_KN = 9.81              # 1 Ton = 9.81 kN  → kN / 9.81 = Ton
VALID_OUTPUT_UNITS = ("kN", "Ton")

# ---------------------------------------------------------------------------
# Numerical tolerances (Core 1)
# ---------------------------------------------------------------------------
ZERO_TOL = 1e-12             # divisor threshold for zero-division protection
VALIDATION_RTOL = 1e-3       # golden-file / validation-case relative tolerance

# ---------------------------------------------------------------------------
# Column / Field Definitions
# ---------------------------------------------------------------------------
PILE_COLUMNS = ["Pile_ID", "X", "Y"]                              # coordinates CSV (X, Y in m)
LC_COLUMNS = ["LC_ID", "Fx", "Fy", "Fz", "Mx", "My", "Mz"]        # load cases CSV (kN, kN·m)
PILE_NUMERIC_COLUMNS = ["X", "Y"]
LC_NUMERIC_COLUMNS = ["Fx", "Fy", "Fz", "Mx", "My", "Mz"]
MASTER_COLUMNS = ["LC_ID", "Pile_ID", "X", "Y", "Axial_Force", "Hx", "Hy", "H_Resultant"]

# Force columns subject to kN→Ton conversion at the output boundary.
MASTER_FORCE_COLUMNS = ["Axial_Force", "Hx", "Hy", "H_Resultant"]
ENVELOPE_FORCE_COLUMNS = [
    "Max_Compression", "Max_Tension",
    "Max_Lateral", "Max_Lat_Hx", "Max_Lat_Hy",
    "Min_Lateral", "Min_Lat_Hx", "Min_Lat_Hy",
]

VALID_PILE_SHAPES = ("Circle", "Square")
VALID_CENTROID_MODES = ("Auto", "Manual")

# ---------------------------------------------------------------------------
# Design Parameter Defaults
# (base layer of the merge: config -> params.json -> CLI flags)
# ---------------------------------------------------------------------------
DEFAULT_PARAMS = {
    # Pilecap
    "pilecap_length": 5.0,      # m
    "pilecap_width": 5.0,       # m
    "pilecap_height": 1.5,      # m (thickness)
    "gamma_concrete": 24.0,     # kN/m³
    # Soil backfill
    "soil_height": 1.0,         # m
    "gamma_soil": 18.0,         # kN/m³
    # Pile
    "pile_shape": "Circle",     # Circle | Square
    "pile_dim": 0.6,            # m (diameter for Circle, width for Square)
    "pile_length": 20.0,        # m
    "gamma_pile": 24.0,         # kN/m³
    # Centroid
    "centroid_mode": "Auto",    # Auto | Manual
    "x_centroid": 0.0,          # m (used only when centroid_mode == Manual)
    "y_centroid": 0.0,          # m
    # Output
    "output_unit": "kN",        # kN | Ton
}

# ---------------------------------------------------------------------------
# Output Settings
# ---------------------------------------------------------------------------
OUTPUT_FOLDER = "output"       # default parent folder for timestamped runs
OUTPUT_PREFIX = "pile_forces"  # -> output/pile_forces_YYYYMMDD_HHMMSS/
OUTPUT_DPI = 300
FIGSIZE = (10.0, 8.0)          # inches
PLOT_GRID_DTICK = 0.5          # grid interval (m), matches Streamlit plots

# --- Plot palette (mirrors the Plotly frontend) ---
COLOR_COMPRESSION = "#ef4444"  # warm red   — positive axial (compression)
COLOR_TENSION = "#3b82f6"      # cool blue  — negative axial (tension)
COLOR_CENTROID = "#facc15"     # gold cross — group centroid
COLOR_PILE_MARKER = "#64748b"  # slate      — plain pile marker
COLOR_ARROW = "#10b981"        # emerald    — lateral force vectors
COLOR_GRID = "#cbd5e1"
COLOR_TEXT = "#0f172a"

# Bubble sizing (matplotlib scatter uses point-area `s`; base + proportional).
BUBBLE_MIN_AREA = 200.0        # min marker area for non-zero forces
BUBBLE_MAX_EXTRA_AREA = 2800.0 # extra area at |force| == max

# ---------------------------------------------------------------------------
# Provenance / Standards (Core 5)
# ---------------------------------------------------------------------------
STANDARDS = {
    "method": "Rigid pilecap — pile-group polar inertia distribution",
    "axial": "P_i = P_total/n - Mx·y_i/Sum(y^2) + My·x_i/Sum(x^2) + W_pile",
    "lateral": "Hx_i = Fx/n - Mz·y_i/I_polar ; Hy_i = Fy/n + Mz·x_i/I_polar",
    "references": [
        "Elastic pile-group analysis (rigid cap assumption)",
        "Bowles, Foundation Analysis and Design, pile group reactions",
    ],
}
