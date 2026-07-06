"""
Pile Forces Calculator Dashboard — Streamlit Application.

Main entry point: `streamlit run app.py`

Distributes structural reaction forces (from Midas Civil) into individual
pile foundation forces using pile group polar inertia.
"""

import os
import tempfile

import pandas as pd
import streamlit as st

from pile_forces.domain_engine import (
    build_envelope,
    build_master_output,
)
from pile_forces.io_utils import convert_units
from pile_forces.math_engine import calc_centroid
from pile_forces.plotly_viz import (
    export_figure_to_png,
    plot_axial_bubbles,
    plot_envelope_axial,
    plot_envelope_lateral,
    plot_lateral_vectors,
)
from pile_forces.reporter import (
    compile_report_to_pdf,
    generate_typst_report,
)
from pile_forces.state_manager import (
    export_state,
    import_state,
)


def _centroid_of(df):
    """Centroid from a pile DataFrame (numeric-coerced), for the Streamlit UI."""
    x_arr = pd.to_numeric(df["X"], errors="coerce").dropna().to_numpy()
    y_arr = pd.to_numeric(df["Y"], errors="coerce").dropna().to_numpy()
    return calc_centroid(x_arr, y_arr)


# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Pile Forces Calculator",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# (Native Streamlit theme used)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

def _init_session_state():
    """Initialize all session state variables with defaults."""
    defaults = {
        # Pilecap
        "pilecap_length": 5.0,
        "pilecap_width": 5.0,
        "pilecap_height": 1.5,
        "gamma_concrete": 24.0,
        # Soil
        "soil_height": 1.0,
        "gamma_soil": 18.0,
        # Pile
        "pile_shape": "Circle",
        "pile_dim": 0.6,
        "pile_length": 20.0,
        "gamma_pile": 24.0,
        # Centroid
        "centroid_mode": "Auto",
        "x_centroid": 0.0,
        "y_centroid": 0.0,
        # Output
        "output_unit": "kN",
        # UI
        "show_labels": True,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Default pile coordinates (4-pile group)
    if "df_piles" not in st.session_state:
        st.session_state["df_piles"] = pd.DataFrame({
            "Pile_ID": ["P1", "P2", "P3", "P4"],
            "X": [0.0, 3.0, 0.0, 3.0],
            "Y": [0.0, 0.0, 3.0, 3.0],
        })

    # Default load cases
    if "df_lc" not in st.session_state:
        st.session_state["df_lc"] = pd.DataFrame({
            "LC_ID": ["LC1"],
            "Fx": [100.0],
            "Fy": [50.0],
            "Fz": [1000.0],
            "Mx": [200.0],
            "My": [150.0],
            "Mz": [80.0],
        })


_init_session_state()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🏗️ Project Settings")

    # --- Save / Load ---
    st.markdown("### 💾 Project State")

    params_for_save = {
        k: st.session_state[k]
        for k in [
            "pilecap_length", "pilecap_width", "pilecap_height", "gamma_concrete",
            "soil_height", "gamma_soil",
            "pile_shape", "pile_dim", "pile_length", "gamma_pile",
            "centroid_mode", "x_centroid", "y_centroid",
            "output_unit",
        ]
    }
    json_str = export_state(
        params_for_save,
        st.session_state["df_piles"],
        st.session_state["df_lc"],
    )
    st.download_button(
        label="📥 Save Project",
        data=json_str,
        file_name="pile_design_state.json",
        mime="application/json",
        key="btn_save_project",
    )

    uploaded_json = st.file_uploader(
        "📂 Load Project (.json)", type=["json"], key="upload_project",
    )
    if uploaded_json is not None:
        try:
            loaded_params, loaded_piles, loaded_lc = import_state(uploaded_json.read())
            for key, val in loaded_params.items():
                if key in st.session_state:
                    st.session_state[key] = val
            st.session_state["df_piles"] = loaded_piles
            st.session_state["df_lc"] = loaded_lc
            st.success("✅ Project loaded!")
            st.rerun()
        except ValueError as exc:
            st.error(f"❌ {exc}")

    st.divider()

    # --- Pilecap ---
    st.markdown("### 📐 Pilecap Dimensions")
    st.session_state["pilecap_length"] = st.number_input(
        "Length (m)", value=st.session_state["pilecap_length"],
        min_value=0.1, step=0.5, format="%.2f", key="inp_pc_l",
    )
    st.session_state["pilecap_width"] = st.number_input(
        "Width (m)", value=st.session_state["pilecap_width"],
        min_value=0.1, step=0.5, format="%.2f", key="inp_pc_w",
    )
    st.session_state["pilecap_height"] = st.number_input(
        "Height / Thickness (m)", value=st.session_state["pilecap_height"],
        min_value=0.1, step=0.1, format="%.2f", key="inp_pc_h",
    )
    st.session_state["gamma_concrete"] = st.number_input(
        "γ Concrete (kN/m³)", value=st.session_state["gamma_concrete"],
        min_value=1.0, step=0.5, format="%.1f", key="inp_gc",
    )

    st.divider()

    # --- Soil ---
    st.markdown("### 🌍 Soil Backfill")
    st.session_state["soil_height"] = st.number_input(
        "Fill Height (m)", value=st.session_state["soil_height"],
        min_value=0.0, step=0.5, format="%.2f", key="inp_sh",
    )
    st.session_state["gamma_soil"] = st.number_input(
        "γ Soil (kN/m³)", value=st.session_state["gamma_soil"],
        min_value=1.0, step=0.5, format="%.1f", key="inp_gs",
    )

    st.divider()

    # --- Pile ---
    st.markdown("### 🪵 Pile Dimensions")
    st.session_state["pile_shape"] = st.selectbox(
        "Pile Shape", ["Circle", "Square"],
        index=0 if st.session_state["pile_shape"] == "Circle" else 1,
        key="inp_shape",
    )
    dim_label = "Diameter (m)" if st.session_state["pile_shape"] == "Circle" else "Width (m)"
    st.session_state["pile_dim"] = st.number_input(
        dim_label, value=st.session_state["pile_dim"],
        min_value=0.05, step=0.1, format="%.3f", key="inp_dim",
    )
    st.session_state["pile_length"] = st.number_input(
        "Pile Length (m)", value=st.session_state["pile_length"],
        min_value=0.5, step=1.0, format="%.2f", key="inp_pl",
    )
    st.session_state["gamma_pile"] = st.number_input(
        "γ Pile (kN/m³)", value=st.session_state["gamma_pile"],
        min_value=1.0, step=0.5, format="%.1f", key="inp_gp",
    )

    st.divider()

    # --- Centroid ---
    st.markdown("### 🎯 Centroid Configuration")
    st.session_state["centroid_mode"] = st.radio(
        "Centroid Calculation",
        ["Auto", "Manual"],
        index=0 if st.session_state["centroid_mode"] == "Auto" else 1,
        key="inp_centroid",
        horizontal=True,
    )
    if st.session_state["centroid_mode"] == "Manual":
        st.session_state["x_centroid"] = st.number_input(
            "X Centroid (m)", value=st.session_state["x_centroid"],
            step=0.1, format="%.3f", key="inp_xc",
        )
        st.session_state["y_centroid"] = st.number_input(
            "Y Centroid (m)", value=st.session_state["y_centroid"],
            step=0.1, format="%.3f", key="inp_yc",
        )

    st.divider()

    # --- Output Unit ---
    st.markdown("### 📏 Output Unit")
    st.session_state["output_unit"] = st.selectbox(
        "Force Unit", ["kN", "Ton"],
        index=0 if st.session_state["output_unit"] == "kN" else 1,
        key="inp_unit",
    )

    st.divider()

    # --- Plot toggle ---
    st.session_state["show_labels"] = st.checkbox(
        "Show Force Values on Plot",
        value=st.session_state["show_labels"],
        key="inp_labels",
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🏗️ Pile Forces Calculator")
st.markdown("Automated distribution of structural reaction forces into individual pile foundation forces")


# ---------------------------------------------------------------------------
# Main Tabs
# ---------------------------------------------------------------------------

tab_input, tab_results, tab_lateral, tab_axial, tab_envelope, tab_report = st.tabs([
    "📥 Input Data",
    "📊 Results",
    "📈 Lateral Vectors",
    "🔴 Axial Bubbles",
    "📋 Envelope",
    "📄 Report",
])


# ========================== TAB: Input Data ================================

with tab_input:
    st.subheader("Pile Coordinates & Load Cases")

    col_piles, col_lc = st.columns(2)

    with col_piles:
        st.markdown("**Table 1: Pile Coordinates** (m)")

        with st.expander("📁 Import from CSV", expanded=False):
            uploaded_piles_csv = st.file_uploader(
                "Choose pile coordinates CSV", type=["csv"], key="upload_piles",
            )
            if uploaded_piles_csv is not None:
                try:
                    df_uploaded = pd.read_csv(uploaded_piles_csv)
                    required = {"Pile_ID", "X", "Y"}
                    if required.issubset(set(df_uploaded.columns)):
                        st.session_state["df_piles"] = df_uploaded[list(required)]
                        st.success("✅ Pile coordinates loaded from CSV")
                    else:
                        st.error(f"❌ CSV harus memiliki kolom: {required}")
                except Exception as exc:
                    st.error(f"❌ Error membaca CSV: {exc}")

        edited_piles = st.data_editor(
            st.session_state["df_piles"],
            num_rows="dynamic",
            width="stretch",
            key="editor_piles",
        )
        st.session_state["df_piles"] = edited_piles

    with col_lc:
        st.markdown("**Table 2: Load Cases** (kN, kN·m)")

        with st.expander("📁 Import from CSV", expanded=False):
            uploaded_lc_csv = st.file_uploader(
                "Choose load cases CSV", type=["csv"], key="upload_lc",
            )
            if uploaded_lc_csv is not None:
                try:
                    df_uploaded_lc = pd.read_csv(uploaded_lc_csv)
                    required_lc = {"LC_ID", "Fx", "Fy", "Fz", "Mx", "My", "Mz"}
                    if required_lc.issubset(set(df_uploaded_lc.columns)):
                        st.session_state["df_lc"] = df_uploaded_lc[list(required_lc)]
                        st.success("✅ Load cases loaded from CSV")
                    else:
                        st.error(f"❌ CSV harus memiliki kolom: {required_lc}")
                except Exception as exc:
                    st.error(f"❌ Error membaca CSV: {exc}")

        edited_lc = st.data_editor(
            st.session_state["df_lc"],
            num_rows="dynamic",
            width="stretch",
            key="editor_lc",
        )
        st.session_state["df_lc"] = edited_lc

    # --- Quick info ---
    st.divider()
    info_cols = st.columns(4)
    with info_cols[0]:
        st.metric("Total Piles", len(st.session_state["df_piles"]))
    with info_cols[1]:
        st.metric("Load Cases", len(st.session_state["df_lc"]))
    with info_cols[2]:
        if st.session_state["centroid_mode"] == "Auto":
            x_c, y_c = _centroid_of(st.session_state["df_piles"])
        else:
            x_c = st.session_state["x_centroid"]
            y_c = st.session_state["y_centroid"]
        st.metric("Centroid X", f"{x_c:.3f} m")
    with info_cols[3]:
        st.metric("Centroid Y", f"{y_c:.3f} m")


# ========================== Calculation Engine =============================

# Build parameters dict
params = {
    "pilecap_length": st.session_state["pilecap_length"],
    "pilecap_width": st.session_state["pilecap_width"],
    "pilecap_height": st.session_state["pilecap_height"],
    "gamma_concrete": st.session_state["gamma_concrete"],
    "soil_height": st.session_state["soil_height"],
    "gamma_soil": st.session_state["gamma_soil"],
    "pile_shape": st.session_state["pile_shape"],
    "pile_dim": st.session_state["pile_dim"],
    "pile_length": st.session_state["pile_length"],
    "gamma_pile": st.session_state["gamma_pile"],
    "centroid_mode": st.session_state["centroid_mode"],
    "x_centroid": st.session_state["x_centroid"],
    "y_centroid": st.session_state["y_centroid"],
}

df_piles = st.session_state["df_piles"].copy()
df_lc = st.session_state["df_lc"].copy()

# Validate data before running calculation
can_calculate = (
    len(df_piles) > 0
    and len(df_lc) > 0
    and {"Pile_ID", "X", "Y"}.issubset(set(df_piles.columns))
    and {"LC_ID", "Fx", "Fy", "Fz", "Mx", "My", "Mz"}.issubset(set(df_lc.columns))
)

if can_calculate:
    try:
        # Ensure numeric types
        for col in ["X", "Y"]:
            df_piles[col] = pd.to_numeric(df_piles[col], errors="coerce")
        for col in ["Fx", "Fy", "Fz", "Mx", "My", "Mz"]:
            df_lc[col] = pd.to_numeric(df_lc[col], errors="coerce")

        df_piles = df_piles.dropna(subset=["Pile_ID", "X", "Y"])
        df_lc = df_lc.dropna(subset=["LC_ID", "Fx", "Fy", "Fz", "Mx", "My", "Mz"])

        df_master = build_master_output(df_piles, df_lc, params)
        df_envelope = build_envelope(df_master)

        # Determine centroid for plots
        if params["centroid_mode"] == "Auto":
            centroid = _centroid_of(df_piles)
        else:
            centroid = (params["x_centroid"], params["y_centroid"])

        unit = st.session_state["output_unit"]

        # Apply unit conversion for display
        df_master_display = convert_units(df_master, unit)
        df_envelope_display = convert_units(df_envelope, unit)

        calculation_ok = True
    except Exception as exc:
        st.error(f"❌ Calculation error: {exc}")
        calculation_ok = False
else:
    calculation_ok = False


# ========================== TAB: Results ===================================

with tab_results:
    if calculation_ok:
        st.subheader(f"Master Output ({unit})")

        st.dataframe(
            df_master_display.style.format({
                "X": "{:.3f}", "Y": "{:.3f}",
                "Axial_Force": "{:.2f}", "Hx": "{:.2f}",
                "Hy": "{:.2f}", "H_Resultant": "{:.2f}",
            }),
            width="stretch",
            height=400,
        )

        # CSV Download
        csv_data = df_master_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Results CSV",
            data=csv_data,
            file_name="pile_forces_results.csv",
            mime="text/csv",
        )

        # Summary metrics
        st.divider()
        st.markdown("**Quick Summary**")
        sum_cols = st.columns(4)
        with sum_cols[0]:
            st.metric("Max Compression", f"{df_master_display['Axial_Force'].max():.2f} {unit}")
        with sum_cols[1]:
            st.metric("Max Tension", f"{df_master_display['Axial_Force'].min():.2f} {unit}")
        with sum_cols[2]:
            st.metric("Max Lateral", f"{df_master_display['H_Resultant'].max():.2f} {unit}")
        with sum_cols[3]:
            st.metric("Total Combinations", f"{len(df_master_display)}")
    else:
        st.info("📝 Masukkan data pile coordinates dan load cases pada tab Input Data.")


# ========================== TAB: Lateral Vectors ===========================

with tab_lateral:
    if calculation_ok:
        st.subheader("Lateral Force Vectors — Top-Down View")

        lc_ids = df_master["LC_ID"].unique().tolist()
        selected_lc_lat = st.selectbox(
            "Select Load Case", lc_ids, key="sel_lc_lat",
        )

        df_lc_subset = df_master_display[df_master_display["LC_ID"] == selected_lc_lat].copy()

        fig_lateral = plot_lateral_vectors(
            df_lc_subset,
            centroid,
            show_labels=st.session_state["show_labels"],
            unit=unit,
        )

        st.plotly_chart(
            fig_lateral,
            width="stretch",
            config={
                "displayModeBar": True,
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": f"lateral_vectors_{selected_lc_lat}",
                    "height": 800,
                    "width": 1200,
                    "scale": 2,
                },
            },
        )
    else:
        st.info("📝 Masukkan data pada tab Input Data untuk melihat visualisasi.")


# ========================== TAB: Axial Bubbles =============================

with tab_axial:
    if calculation_ok:
        st.subheader("Axial Force Distribution — Bubble Plot")

        lc_ids_ax = df_master["LC_ID"].unique().tolist()
        selected_lc_ax = st.selectbox(
            "Select Load Case", lc_ids_ax, key="sel_lc_ax",
        )

        df_ax_subset = df_master_display[df_master_display["LC_ID"] == selected_lc_ax].copy()

        fig_axial = plot_axial_bubbles(
            df_ax_subset,
            centroid,
            show_labels=st.session_state["show_labels"],
            unit=unit,
        )

        st.plotly_chart(
            fig_axial,
            width="stretch",
            config={
                "displayModeBar": True,
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": f"axial_bubbles_{selected_lc_ax}",
                    "height": 800,
                    "width": 1200,
                    "scale": 2,
                },
            },
        )

        # Legend explanation
        st.markdown("""
        <div style="display: flex; gap: 24px; align-items: center; padding: 8px 0;">
            <span style="color: #ef4444; font-weight: 600;">🔴 Compression (+)</span>
            <span style="color: #3b82f6; font-weight: 600;">🔵 Tension (−)</span>
            <span style="color: #fbbf24; font-weight: 600;">✚ Centroid</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("📝 Masukkan data pada tab Input Data untuk melihat visualisasi.")


# ========================== TAB: Envelope ==================================

with tab_envelope:
    if calculation_ok:
        st.subheader(f"Governing Load Cases — Envelope Summary ({unit})")

        st.dataframe(
            df_envelope_display.style.format({
                col: "{:.2f}" for col in ["Max_Compression", "Max_Tension", "Max_Lateral"]
                if col in df_envelope_display.columns
            }),
            width="stretch",
        )

        # CSV Download
        csv_env = df_envelope_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Envelope CSV",
            data=csv_env,
            file_name="pile_forces_envelope.csv",
            mime="text/csv",
        )

        # Highlight critical values
        st.divider()
        st.markdown("**Critical Values Across All Piles**")
        crit_cols = st.columns(3)
        with crit_cols[0]:
            max_comp_val = df_envelope_display["Max_Compression"].max()
            max_comp_pile = df_envelope_display.loc[
                df_envelope_display["Max_Compression"].idxmax(), "Pile_ID"
            ]
            st.metric(
                "Highest Compression",
                f"{max_comp_val:.2f} {unit}",
                delta=f"Pile {max_comp_pile}",
                delta_color="off",
            )
        with crit_cols[1]:
            max_tens_val = df_envelope_display["Max_Tension"].min()
            max_tens_pile = df_envelope_display.loc[
                df_envelope_display["Max_Tension"].idxmin(), "Pile_ID"
            ]
            st.metric(
                "Highest Tension",
                f"{max_tens_val:.2f} {unit}",
                delta=f"Pile {max_tens_pile}",
                delta_color="off",
            )
        with crit_cols[2]:
            max_lat_val = df_envelope_display["Max_Lateral"].max()
            max_lat_pile = df_envelope_display.loc[
                df_envelope_display["Max_Lateral"].idxmax(), "Pile_ID"
            ]
            st.metric(
                "Highest Lateral",
                f"{max_lat_val:.2f} {unit}",
                delta=f"Pile {max_lat_pile}",
                delta_color="off",
            )

        # --- Envelope Visualizations ---
        st.divider()
        st.markdown("**Envelope Diagrams**")

        # 1. Max Compression (Axial Bubble)
        fig_env_comp = plot_envelope_axial(
            df_envelope_display, centroid, env_type="Max",
            show_labels=st.session_state["show_labels"], unit=unit,
        )
        st.plotly_chart(
            fig_env_comp, width="stretch",
            config={"displayModeBar": True, "toImageButtonOptions": {"format": "png", "filename": "env_comp", "scale": 2}},
        )

        # 2. Max Tension (Axial Bubble)
        fig_env_tens = plot_envelope_axial(
            df_envelope_display, centroid, env_type="Min",
            show_labels=st.session_state["show_labels"], unit=unit,
        )
        st.plotly_chart(
            fig_env_tens, width="stretch",
            config={"displayModeBar": True, "toImageButtonOptions": {"format": "png", "filename": "env_tens", "scale": 2}},
        )

        # 3. Max Lateral (Vector)
        fig_env_lat_max = plot_envelope_lateral(
            df_envelope_display, centroid, env_type="Max",
            show_labels=st.session_state["show_labels"], unit=unit,
        )
        st.plotly_chart(
            fig_env_lat_max, width="stretch",
            config={"displayModeBar": True, "toImageButtonOptions": {"format": "png", "filename": "env_lat_max", "scale": 2}},
        )

        # 4. Min Lateral (Vector)
        fig_env_lat_min = plot_envelope_lateral(
            df_envelope_display, centroid, env_type="Min",
            show_labels=st.session_state["show_labels"], unit=unit,
        )
        st.plotly_chart(
            fig_env_lat_min, width="stretch",
            config={"displayModeBar": True, "toImageButtonOptions": {"format": "png", "filename": "env_lat_min", "scale": 2}},
        )
    else:
        st.info("📝 Masukkan data pada tab Input Data untuk melihat envelope.")


# ========================== TAB: Report ====================================

with tab_report:
    if calculation_ok:
        st.subheader("📄 Generate PDF Report")
        st.markdown(
            "Generate a professional technical report with parameters, "
            "methodology, visualizations, and governing load case table."
        )

        report_title = st.text_input(
            "Custom Report Title",
            value="Pile Forces Analysis Report",
            help="This title will be displayed on the first page of the PDF report."
        )

        if st.button("🔄 Generate PDF Report", type="primary", width="stretch"):
            with st.spinner("Generating report..."):
                try:
                    # Export plots to temp PNG files
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        plot_paths = []

                        # Generate plots for all load cases
                        for lc_id in df_master_display["LC_ID"].unique():
                            df_lc_subset = df_master_display[df_master_display["LC_ID"] == lc_id]

                            # Lateral vectors
                            fig_lat = plot_lateral_vectors(
                                df_lc_subset, centroid,
                                show_labels=True, unit=unit,
                            )
                            lat_path = os.path.join(tmp_dir, f"lateral_{lc_id}.png")
                            export_figure_to_png(fig_lat, lat_path)
                            plot_paths.append((lat_path, f"Lateral Force Vectors — LC: {lc_id}"))

                            # Axial bubbles
                            fig_ax = plot_axial_bubbles(
                                df_lc_subset, centroid,
                                show_labels=True, unit=unit,
                            )
                            ax_path = os.path.join(tmp_dir, f"axial_{lc_id}.png")
                            export_figure_to_png(fig_ax, ax_path)
                            plot_paths.append((ax_path, f"Axial Force Distribution — LC: {lc_id}"))

                        # Envelope Plots
                        fig_env_comp = plot_envelope_axial(df_envelope_display, centroid, env_type="Max", unit=unit)
                        env_comp_path = os.path.join(tmp_dir, "env_comp.png")
                        export_figure_to_png(fig_env_comp, env_comp_path)
                        plot_paths.append((env_comp_path, "Envelope — Max Axial Compression"))

                        fig_env_tens = plot_envelope_axial(df_envelope_display, centroid, env_type="Min", unit=unit)
                        env_tens_path = os.path.join(tmp_dir, "env_tens.png")
                        export_figure_to_png(fig_env_tens, env_tens_path)
                        plot_paths.append((env_tens_path, "Envelope — Max Axial Tension"))

                        fig_env_lat_max = plot_envelope_lateral(df_envelope_display, centroid, env_type="Max", unit=unit)
                        env_lat_max_path = os.path.join(tmp_dir, "env_lat_max.png")
                        export_figure_to_png(fig_env_lat_max, env_lat_max_path)
                        plot_paths.append((env_lat_max_path, "Envelope — Max Lateral Resultant"))

                        fig_env_lat_min = plot_envelope_lateral(df_envelope_display, centroid, env_type="Min", unit=unit)
                        env_lat_min_path = os.path.join(tmp_dir, "env_lat_min.png")
                        export_figure_to_png(fig_env_lat_min, env_lat_min_path)
                        plot_paths.append((env_lat_min_path, "Envelope — Min Lateral Resultant"))

                        # Generate Typst source
                        typst_src = generate_typst_report(
                            df_envelope_display,
                            params,
                            plot_paths,
                            unit=unit,
                            report_title=report_title,
                        )

                        # Compile to PDF
                        pdf_bytes = compile_report_to_pdf(typst_src, plot_paths)

                        if pdf_bytes is not None:
                            st.success("✅ Report generated successfully!")
                            st.download_button(
                                label="📥 Download Technical Report (PDF)",
                                data=pdf_bytes,
                                file_name="Pile_Analysis_Report.pdf",
                                mime="application/pdf",
                                width="stretch",
                            )
                        else:
                            st.warning(
                                "⚠️ Package `typst` tidak tersedia. "
                                "Install dengan: `pip install typst`"
                            )
                except Exception as exc:
                    st.error(f"❌ Report generation failed: {exc}")
    else:
        st.info("📝 Masukkan data pada tab Input Data untuk generate report.")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.markdown(
    "<p style='text-align: center; color: #64748b; font-size: 0.8rem;'>"
    "Pile Forces Calculator v0.1 — Built with Streamlit & Python"
    "</p>",
    unsafe_allow_html=True,
)
