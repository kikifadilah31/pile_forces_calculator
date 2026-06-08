"""
Plotly visualization functions for pile force distribution.

Provides:
- 2D top-down lateral force vector plot
- Axial force bubble plot (compression vs tension)
- Static PNG export via kaleido
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
_COLOR_COMPRESSION = "rgba(239, 68, 68, 0.85)"      # warm red
_COLOR_TENSION = "rgba(59, 130, 246, 0.85)"          # cool blue
_COLOR_CENTROID = "rgba(250, 204, 21, 1.0)"          # gold
_COLOR_PILE_MARKER = "rgba(100, 116, 139, 0.8)"      # slate
_COLOR_ARROW = "rgba(16, 185, 129, 0.9)"             # emerald
_COLOR_BG = "rgba(15, 23, 42, 1.0)"                  # dark slate
_COLOR_GRID = "rgba(51, 65, 85, 0.5)"                # subtle grid


def _base_layout(title: str) -> dict:
    """Shared dark-theme layout for all plots."""
    return dict(
        title=dict(
            text=title,
            font=dict(size=18, color="white", family="Inter, sans-serif"),
            x=0.5,
        ),
        paper_bgcolor=_COLOR_BG,
        plot_bgcolor="rgba(30, 41, 59, 1.0)",
        font=dict(color="white", family="Inter, sans-serif"),
        xaxis=dict(
            title="X (m)",
            scaleanchor="y",
            scaleratio=1,
            gridcolor=_COLOR_GRID,
            zerolinecolor=_COLOR_GRID,
        ),
        yaxis=dict(
            title="Y (m)",
            gridcolor=_COLOR_GRID,
            zerolinecolor=_COLOR_GRID,
        ),
        legend=dict(
            bgcolor="rgba(30, 41, 59, 0.8)",
            bordercolor="rgba(100, 116, 139, 0.5)",
            borderwidth=1,
        ),
        margin=dict(l=60, r=40, t=60, b=60),
    )


# ---------------------------------------------------------------------------
# Lateral Force Vector Plot
# ---------------------------------------------------------------------------

def plot_lateral_vectors(
    df_lc_subset: pd.DataFrame,
    centroid: tuple[float, float],
    show_labels: bool = True,
    unit: str = "kN",
) -> go.Figure:
    """Create 2D top-down plot with lateral force vector arrows.

    Parameters
    ----------
    df_lc_subset : DataFrame filtered to a single LC_ID with columns
        [Pile_ID, X, Y, Hx, Hy, H_Resultant]
    centroid : (x_c, y_c) tuple
    show_labels : whether to show H_Resultant text near arrow tips
    unit : display unit string for labels

    Returns
    -------
    plotly Figure
    """
    lc_id = df_lc_subset["LC_ID"].iloc[0] if "LC_ID" in df_lc_subset.columns else "N/A"

    fig = go.Figure()

    # --- Pile markers ---
    fig.add_trace(go.Scatter(
        x=df_lc_subset["X"],
        y=df_lc_subset["Y"],
        mode="markers+text",
        marker=dict(size=12, color=_COLOR_PILE_MARKER, symbol="square",
                    line=dict(width=1.5, color="white")),
        text=df_lc_subset["Pile_ID"].astype(str),
        textposition="top center",
        textfont=dict(size=10, color="white"),
        name="Piles",
        hovertemplate=(
            "<b>Pile %{text}</b><br>"
            "X: %{x:.3f} m<br>"
            "Y: %{y:.3f} m<br>"
            "<extra></extra>"
        ),
    ))

    # --- Centroid marker ---
    fig.add_trace(go.Scatter(
        x=[centroid[0]],
        y=[centroid[1]],
        mode="markers",
        marker=dict(size=16, color=_COLOR_CENTROID, symbol="cross-thin",
                    line=dict(width=2, color=_COLOR_CENTROID)),
        name="Centroid",
        hovertemplate="<b>Centroid</b><br>X: %{x:.3f}<br>Y: %{y:.3f}<extra></extra>",
    ))

    # --- Force vector arrows ---
    max_h = df_lc_subset["H_Resultant"].max()
    # Scale factor: normalize arrow length relative to pile spacing
    x_range = df_lc_subset["X"].max() - df_lc_subset["X"].min()
    y_range = df_lc_subset["Y"].max() - df_lc_subset["Y"].min()
    plot_span = max(x_range, y_range, 1.0)
    scale = (plot_span * 0.3) / max(max_h, 1e-6)

    annotations = []
    for _, row in df_lc_subset.iterrows():
        dx = row["Hx"] * scale
        dy = row["Hy"] * scale
        tip_x = row["X"] + dx
        tip_y = row["Y"] + dy

        annotations.append(dict(
            x=tip_x,
            y=tip_y,
            ax=row["X"],
            ay=row["Y"],
            xref="x", yref="y",
            axref="x", ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.5,
            arrowwidth=2.5,
            arrowcolor=_COLOR_ARROW,
        ))

        if show_labels and row["H_Resultant"] > 1e-6:
            annotations.append(dict(
                x=tip_x,
                y=tip_y,
                text=f"<b>{row['H_Resultant']:.1f}</b> {unit}",
                showarrow=False,
                font=dict(size=10, color=_COLOR_ARROW),
                xshift=10,
                yshift=10,
                bgcolor="rgba(15, 23, 42, 0.7)",
                borderpad=2,
            ))

    layout = _base_layout(f"Lateral Force Vectors — LC: {lc_id}")
    layout["annotations"] = annotations

    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------------
# Axial Force Bubble Plot
# ---------------------------------------------------------------------------

def plot_axial_bubbles(
    df_lc_subset: pd.DataFrame,
    centroid: tuple[float, float],
    show_labels: bool = True,
    unit: str = "kN",
) -> go.Figure:
    """Create bubble plot for axial forces — size ∝ |Axial|, color = tension/compression.

    Parameters
    ----------
    df_lc_subset : DataFrame filtered to single LC_ID with columns
        [Pile_ID, X, Y, Axial_Force, LC_ID]
    centroid : (x_c, y_c)
    show_labels : show force values inside bubbles
    unit : display unit

    Returns
    -------
    plotly Figure
    """
    lc_id = df_lc_subset["LC_ID"].iloc[0] if "LC_ID" in df_lc_subset.columns else "N/A"

    abs_force = df_lc_subset["Axial_Force"].abs()
    max_force = abs_force.max() if abs_force.max() > 1e-6 else 1.0

    # Bubble size: minimum 15px, max 60px, scaled proportionally
    bubble_sizes = 15 + (abs_force / max_force) * 45

    # Color: compression (positive) = red, tension (negative) = blue
    colors = np.where(
        df_lc_subset["Axial_Force"].values >= 0,
        _COLOR_COMPRESSION,
        _COLOR_TENSION,
    )

    fig = go.Figure()

    # --- Compression piles ---
    mask_comp = df_lc_subset["Axial_Force"] >= 0
    if mask_comp.any():
        df_comp = df_lc_subset[mask_comp]
        fig.add_trace(go.Scatter(
            x=df_comp["X"],
            y=df_comp["Y"],
            mode="markers",
            marker=dict(
                size=bubble_sizes[mask_comp],
                color=_COLOR_COMPRESSION,
                line=dict(width=1.5, color="white"),
                opacity=0.85,
            ),
            name="Compression (+)",
            customdata=np.column_stack([
                df_comp["Pile_ID"].values,
                df_comp["Axial_Force"].values,
                [lc_id] * mask_comp.sum(),
            ]),
            hovertemplate=(
                "<b>Pile %{customdata[0]}</b><br>"
                "X: %{x:.3f} m<br>"
                "Y: %{y:.3f} m<br>"
                "Axial: %{customdata[1]:.2f} " + unit + "<br>"
                "LC: %{customdata[2]}<br>"
                "<extra></extra>"
            ),
        ))

    # --- Tension piles ---
    mask_tens = df_lc_subset["Axial_Force"] < 0
    if mask_tens.any():
        df_tens = df_lc_subset[mask_tens]
        fig.add_trace(go.Scatter(
            x=df_tens["X"],
            y=df_tens["Y"],
            mode="markers",
            marker=dict(
                size=bubble_sizes[mask_tens],
                color=_COLOR_TENSION,
                line=dict(width=1.5, color="white"),
                opacity=0.85,
            ),
            name="Tension (−)",
            customdata=np.column_stack([
                df_tens["Pile_ID"].values,
                df_tens["Axial_Force"].values,
                [lc_id] * mask_tens.sum(),
            ]),
            hovertemplate=(
                "<b>Pile %{customdata[0]}</b><br>"
                "X: %{x:.3f} m<br>"
                "Y: %{y:.3f} m<br>"
                "Axial: %{customdata[1]:.2f} " + unit + "<br>"
                "LC: %{customdata[2]}<br>"
                "<extra></extra>"
            ),
        ))

    # --- Centroid marker ---
    fig.add_trace(go.Scatter(
        x=[centroid[0]],
        y=[centroid[1]],
        mode="markers",
        marker=dict(size=16, color=_COLOR_CENTROID, symbol="cross-thin",
                    line=dict(width=2, color=_COLOR_CENTROID)),
        name="Centroid",
        hovertemplate="<b>Centroid</b><br>X: %{x:.3f}<br>Y: %{y:.3f}<extra></extra>",
    ))

    # --- Static text annotations (for PDF/PNG export) ---
    annotations = []
    if show_labels:
        for idx, row in df_lc_subset.iterrows():
            annotations.append(dict(
                x=row["X"],
                y=row["Y"],
                text=f"<b>{row['Axial_Force']:.1f}</b>",
                showarrow=False,
                font=dict(
                    size=9,
                    color="white",
                    family="Inter, sans-serif",
                ),
                bgcolor="rgba(0, 0, 0, 0.5)",
                borderpad=2,
            ))

    layout = _base_layout(f"Axial Force Distribution — LC: {lc_id}")
    layout["annotations"] = annotations

    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------------
# Envelope Visualizations
# ---------------------------------------------------------------------------

def plot_envelope_axial(
    df_envelope: pd.DataFrame,
    centroid: tuple[float, float],
    show_labels: bool = True,
    unit: str = "kN",
) -> go.Figure:
    """Create grouped bar chart showing Max Compression and Max Tension per pile.

    Parameters
    ----------
    df_envelope : Envelope DataFrame with columns
        [Pile_ID, Max_Compression, LC_Max_Comp, Max_Tension, LC_Max_Tens, ...]
    centroid : (x_c, y_c)
    show_labels : whether to show values on bars
    unit : display unit
    """
    fig = go.Figure()

    pile_ids = df_envelope["Pile_ID"].astype(str).tolist()

    # Max Compression bars (positive = compression)
    fig.add_trace(go.Bar(
        x=pile_ids,
        y=df_envelope["Max_Compression"],
        name="Max Compression",
        marker=dict(
            color="rgba(239, 68, 68, 0.85)",
            line=dict(width=1, color="rgba(239, 68, 68, 1.0)"),
        ),
        text=[f"{v:.1f}" for v in df_envelope["Max_Compression"]] if show_labels else None,
        textposition="outside",
        textfont=dict(size=10, color="rgba(239, 68, 68, 1.0)"),
        customdata=df_envelope["LC_Max_Comp"].values,
        hovertemplate=(
            "<b>Pile %{x}</b><br>"
            "Max Compression: %{y:.2f} " + unit + "<br>"
            "LC: %{customdata}<br>"
            "<extra></extra>"
        ),
    ))

    # Max Tension bars (negative = tension)
    fig.add_trace(go.Bar(
        x=pile_ids,
        y=df_envelope["Max_Tension"],
        name="Max Tension",
        marker=dict(
            color="rgba(59, 130, 246, 0.85)",
            line=dict(width=1, color="rgba(59, 130, 246, 1.0)"),
        ),
        text=[f"{v:.1f}" for v in df_envelope["Max_Tension"]] if show_labels else None,
        textposition="outside",
        textfont=dict(size=10, color="rgba(59, 130, 246, 1.0)"),
        customdata=df_envelope["LC_Max_Tens"].values,
        hovertemplate=(
            "<b>Pile %{x}</b><br>"
            "Max Tension: %{y:.2f} " + unit + "<br>"
            "LC: %{customdata}<br>"
            "<extra></extra>"
        ),
    ))

    layout = _base_layout(f"Envelope — Max Axial Forces ({unit})")
    layout.update(
        barmode="group",
        xaxis=dict(
            title="Pile ID",
            gridcolor=_COLOR_GRID,
            zerolinecolor=_COLOR_GRID,
            scaleanchor=None,
        ),
        yaxis=dict(
            title=f"Axial Force ({unit})",
            gridcolor=_COLOR_GRID,
            zerolinecolor="rgba(148, 163, 184, 0.6)",
            zerolinewidth=2,
        ),
    )

    # Add zero line annotation
    fig.update_layout(**layout)

    # Add horizontal line at zero for reference
    fig.add_hline(
        y=0, line_dash="dot",
        line_color="rgba(148, 163, 184, 0.5)",
        line_width=1,
    )

    return fig


def plot_envelope_lateral(
    df_envelope: pd.DataFrame,
    centroid: tuple[float, float],
    show_labels: bool = True,
    unit: str = "kN",
) -> go.Figure:
    """Create bar chart showing Max Lateral Resultant per pile.

    Parameters
    ----------
    df_envelope : Envelope DataFrame with columns
        [Pile_ID, ..., Max_Lateral, LC_Max_Lat]
    centroid : (x_c, y_c)
    show_labels : whether to show values on bars
    unit : display unit
    """
    fig = go.Figure()

    pile_ids = df_envelope["Pile_ID"].astype(str).tolist()

    fig.add_trace(go.Bar(
        x=pile_ids,
        y=df_envelope["Max_Lateral"],
        name="Max Lateral",
        marker=dict(
            color="rgba(16, 185, 129, 0.85)",
            line=dict(width=1, color="rgba(16, 185, 129, 1.0)"),
        ),
        text=[f"{v:.1f}" for v in df_envelope["Max_Lateral"]] if show_labels else None,
        textposition="outside",
        textfont=dict(size=10, color="rgba(16, 185, 129, 1.0)"),
        customdata=df_envelope["LC_Max_Lat"].values,
        hovertemplate=(
            "<b>Pile %{x}</b><br>"
            "Max Lateral: %{y:.2f} " + unit + "<br>"
            "LC: %{customdata}<br>"
            "<extra></extra>"
        ),
    ))

    layout = _base_layout(f"Envelope — Max Lateral Forces ({unit})")
    layout.update(
        xaxis=dict(
            title="Pile ID",
            gridcolor=_COLOR_GRID,
            zerolinecolor=_COLOR_GRID,
            scaleanchor=None,
        ),
        yaxis=dict(
            title=f"Lateral Force ({unit})",
            gridcolor=_COLOR_GRID,
            zerolinecolor=_COLOR_GRID,
        ),
    )

    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------------
# PNG Export
# ---------------------------------------------------------------------------

def export_figure_to_png(fig: go.Figure, path: str, width: int = 1200, height: int = 800) -> None:
    """Export a Plotly figure to a static PNG image using kaleido.

    Parameters
    ----------
    fig : plotly Figure
    path : output file path (e.g., '/tmp/plot.png')
    width : image width in pixels
    height : image height in pixels
    """
    fig.write_image(path, width=width, height=height, engine="kaleido")

