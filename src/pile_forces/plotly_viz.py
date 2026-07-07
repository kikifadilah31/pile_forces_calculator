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
_COLOR_PILECAP = "rgba(21, 128, 61, 1.0)"            # green  — pilecap boundary
_COLOR_PILE_OUTLINE = "rgba(29, 78, 216, 0.9)"       # blue   — true-scale pile footprint
_COLOR_BG = "rgba(255, 255, 255, 1.0)"               # white
_COLOR_GRID = "rgba(203, 213, 225, 0.5)"             # light slate grid
_COLOR_TEXT = "rgba(15, 23, 42, 1.0)"                # dark text
_COLOR_AXIS = "rgba(148, 163, 184, 0.8)"             # axis lines


def _base_layout(title: str) -> dict:
    """Shared light-theme layout for all plots."""
    return dict(
        title=dict(
            text=title,
            font=dict(size=18, color=_COLOR_TEXT, family="Inter, sans-serif"),
            x=0.5,
        ),
        paper_bgcolor=_COLOR_BG,
        plot_bgcolor="rgba(248, 250, 252, 1.0)",
        font=dict(color=_COLOR_TEXT, family="Inter, sans-serif"),
        xaxis=dict(
            title=dict(text="X (m)", font=dict(color=_COLOR_TEXT)),
            gridcolor=_COLOR_GRID,
            zerolinecolor=_COLOR_AXIS,
            showgrid=True,
            tickfont=dict(color=_COLOR_TEXT),
            dtick=0.5,
        ),
        yaxis=dict(
            title=dict(text="Y (m)", font=dict(color=_COLOR_TEXT)),
            scaleanchor="x",
            scaleratio=1,
            gridcolor=_COLOR_GRID,
            zerolinecolor=_COLOR_AXIS,
            showgrid=True,
            tickfont=dict(color=_COLOR_TEXT),
            dtick=0.5,
        ),
        legend=dict(
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="rgba(203, 213, 225, 1.0)",
            borderwidth=1,
            font=dict(color=_COLOR_TEXT),
        ),
        margin=dict(l=60, r=40, t=60, b=60),
    )


# ---------------------------------------------------------------------------
# Shared overlays: pilecap boundary + true-scale pile outlines
# ---------------------------------------------------------------------------

def _add_pilecap_boundary(fig: go.Figure, boundary_xy) -> None:
    """Draw the pilecap outline as a closed green polyline (data-space, m)."""
    if boundary_xy is None or len(boundary_xy) < 3:
        return
    pts = np.asarray(boundary_xy, dtype=float)
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[0]])
    fig.add_trace(go.Scatter(
        x=pts[:, 0], y=pts[:, 1], mode="lines",
        line=dict(color=_COLOR_PILECAP, width=2.5),
        name="Pilecap boundary", hoverinfo="skip",
    ))


def _add_pile_outlines(fig: go.Figure, x_vals, y_vals, pile_shape: str, pile_dim: float) -> None:
    """Draw each pile's true footprint (diameter/side) as a dashed blue outline."""
    if not pile_dim or pile_dim <= 0:
        return
    half = pile_dim / 2.0
    first = True
    for x, y in zip(x_vals, y_vals, strict=True):
        if pile_shape == "Square":
            xs = [x - half, x + half, x + half, x - half, x - half]
            ys = [y - half, y - half, y + half, y + half, y - half]
        else:
            theta = np.linspace(0, 2 * np.pi, 48)
            xs = x + half * np.cos(theta)
            ys = y + half * np.sin(theta)
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines",
            line=dict(color=_COLOR_PILE_OUTLINE, width=1.5, dash="dash"),
            name="Pile (actual size)", legendgroup="pile_outline",
            showlegend=first, hoverinfo="skip",
        ))
        first = False


# ---------------------------------------------------------------------------
# Lateral Force Vector Plot
# ---------------------------------------------------------------------------

def plot_lateral_vectors(
    df_lc_subset: pd.DataFrame,
    centroid: tuple[float, float],
    show_labels: bool = True,
    unit: str = "kN",
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
    pilecap_boundary=None,
) -> go.Figure:
    """Create 2D top-down plot with lateral force vector arrows.

    Parameters
    ----------
    df_lc_subset : DataFrame filtered to a single LC_ID with columns
        [Pile_ID, X, Y, Hx, Hy, H_Resultant]
    centroid : (x_c, y_c) tuple
    show_labels : whether to show H_Resultant text near arrow tips
    unit : display unit string for labels
    pile_shape, pile_dim : draw each pile's true footprint outline (m)
    pilecap_boundary : (n, 2) polygon of the pilecap outline, or None

    Returns
    -------
    plotly Figure
    """
    lc_id = df_lc_subset["LC_ID"].iloc[0] if "LC_ID" in df_lc_subset.columns else "N/A"

    fig = go.Figure()
    _add_pilecap_boundary(fig, pilecap_boundary)

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
                font=dict(size=10, color=_COLOR_TEXT),
                xshift=10,
                yshift=10,
                bgcolor="rgba(255, 255, 255, 0.7)",
                bordercolor="rgba(148, 163, 184, 0.5)",
                borderpad=2,
            ))

    _add_pile_outlines(fig, df_lc_subset["X"], df_lc_subset["Y"], pile_shape, pile_dim)

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
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
    pilecap_boundary=None,
) -> go.Figure:
    """Create bubble plot for axial forces — size ∝ |Axial|, color = tension/compression.

    Parameters
    ----------
    df_lc_subset : DataFrame filtered to single LC_ID with columns
        [Pile_ID, X, Y, Axial_Force, LC_ID]
    centroid : (x_c, y_c)
    show_labels : show force values inside bubbles
    unit : display unit
    pile_shape, pile_dim : draw each pile's true footprint outline (m)
    pilecap_boundary : (n, 2) polygon of the pilecap outline, or None

    Returns
    -------
    plotly Figure
    """
    lc_id = df_lc_subset["LC_ID"].iloc[0] if "LC_ID" in df_lc_subset.columns else "N/A"

    abs_force = df_lc_subset["Axial_Force"].abs()
    max_force = abs_force.max() if abs_force.max() > 1e-6 else 1.0

    # Bubble size: minimum 15px, max 60px, scaled proportionally
    bubble_sizes = np.where(abs_force == 0, 0, 15 + (abs_force / max_force) * 45)

    # Color: compression (positive) = red, tension (negative) = blue.
    # (Per-trace masks below apply the colors; no combined array needed here.)

    fig = go.Figure()
    _add_pilecap_boundary(fig, pilecap_boundary)

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
        for _idx, row in df_lc_subset.iterrows():
            annotations.append(dict(
                x=row["X"],
                y=row["Y"],
                text=f"<b>{row['Axial_Force']:.1f}</b>",
                showarrow=False,
                font=dict(
                    size=10,
                    color=_COLOR_TEXT,
                    family="Inter, sans-serif",
                ),
                bgcolor="rgba(255, 255, 255, 0.7)",
                bordercolor="rgba(148, 163, 184, 0.5)",
                borderpad=2,
            ))

    _add_pile_outlines(fig, df_lc_subset["X"], df_lc_subset["Y"], pile_shape, pile_dim)

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
    env_type: str = "Max",
    show_labels: bool = True,
    unit: str = "kN",
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
    pilecap_boundary=None,
) -> go.Figure:
    """Create bubble plot for Envelope Axial Forces.

    env_type: "Max" (Max Compression) or "Min" (Max Tension)
    """
    fig = go.Figure()
    _add_pilecap_boundary(fig, pilecap_boundary)

    col = "Max_Compression" if env_type == "Max" else "Max_Tension"
    lc_col = "LC_Max_Comp" if env_type == "Max" else "LC_Max_Tens"
    title_suffix = "Max Compression" if env_type == "Max" else "Max Tension"
    
    abs_force = df_envelope[col].abs()
    max_force = abs_force.max() if abs_force.max() > 1e-6 else 1.0

    bubble_sizes = np.where(abs_force == 0, 0, 15 + (abs_force / max_force) * 45)

    # Determine colors
    colors = np.where(
        df_envelope[col].values >= 0,
        _COLOR_COMPRESSION,
        _COLOR_TENSION,
    )

    fig.add_trace(go.Scatter(
        x=df_envelope["X"],
        y=df_envelope["Y"],
        mode="markers",
        marker=dict(
            size=bubble_sizes,
            color=colors,
            line=dict(width=1.5, color="white"),
            opacity=0.85,
        ),
        name=f"{title_suffix} Envelope",
        customdata=np.column_stack([
            df_envelope["Pile_ID"].values,
            df_envelope[col].values,
            df_envelope[lc_col].values,
        ]),
        hovertemplate=(
            "<b>Pile %{customdata[0]}</b><br>"
            "X: %{x:.3f} m<br>"
            "Y: %{y:.3f} m<br>"
            "Axial: %{customdata[1]:.2f} " + unit + "<br>"
            "Gov. LC: %{customdata[2]}<br>"
            "<extra></extra>"
        ),
    ))

    # Centroid
    fig.add_trace(go.Scatter(
        x=[centroid[0]],
        y=[centroid[1]],
        mode="markers",
        marker=dict(size=16, color=_COLOR_CENTROID, symbol="cross-thin", line=dict(width=2, color=_COLOR_CENTROID)),
        name="Centroid",
        hovertemplate="<b>Centroid</b><br>X: %{x:.3f}<br>Y: %{y:.3f}<extra></extra>",
    ))

    annotations = []
    if show_labels:
        for _i, row in df_envelope.iterrows():
            px = row["X"]
            py = row["Y"]
            annotations.append(dict(
                x=px,
                y=py,
                text=f"<b>{row[col]:.1f}</b>",
                showarrow=False,
                font=dict(size=10, color=_COLOR_TEXT, family="Inter, sans-serif"),
                bgcolor="rgba(255, 255, 255, 0.7)",
                bordercolor="rgba(148, 163, 184, 0.5)",
                borderpad=2,
            ))

    _add_pile_outlines(fig, df_envelope["X"], df_envelope["Y"], pile_shape, pile_dim)

    layout = _base_layout(f"Envelope Axial — {title_suffix}")
    layout["annotations"] = annotations

    fig.update_layout(**layout)
    return fig


def plot_envelope_lateral(
    df_envelope: pd.DataFrame,
    centroid: tuple[float, float],
    env_type: str = "Max",
    show_labels: bool = True,
    unit: str = "kN",
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
    pilecap_boundary=None,
) -> go.Figure:
    """Create vector plot for Envelope Lateral Forces.

    env_type: "Max" (Max Lateral) or "Min" (Min Lateral)
    """
    fig = go.Figure()
    _add_pilecap_boundary(fig, pilecap_boundary)

    res_col = "Max_Lateral" if env_type == "Max" else "Min_Lateral"
    hx_col = "Max_Lat_Hx" if env_type == "Max" else "Min_Lat_Hx"
    hy_col = "Max_Lat_Hy" if env_type == "Max" else "Min_Lat_Hy"
    title_suffix = "Max Resultant" if env_type == "Max" else "Min Resultant"

    # Pile markers
    x_vals = df_envelope["X"]
    y_vals = df_envelope["Y"]

    fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode="markers+text",
        marker=dict(size=12, color=_COLOR_PILE_MARKER, symbol="square", line=dict(width=1.5, color="white")),
        text=df_envelope["Pile_ID"].astype(str),
        textposition="top center",
        textfont=dict(size=10, color=_COLOR_TEXT),
        name="Piles",
        hovertemplate="<b>Pile %{text}</b><br>X: %{x:.3f} m<br>Y: %{y:.3f} m<br><extra></extra>",
    ))

    # Centroid
    fig.add_trace(go.Scatter(
        x=[centroid[0]],
        y=[centroid[1]],
        mode="markers",
        marker=dict(size=16, color=_COLOR_CENTROID, symbol="cross-thin", line=dict(width=2, color=_COLOR_CENTROID)),
        name="Centroid",
        hovertemplate="<b>Centroid</b><br>X: %{x:.3f}<br>Y: %{y:.3f}<extra></extra>",
    ))

    # Vector Arrows
    max_h = df_envelope[res_col].max()
    x_range = x_vals.max() - x_vals.min()
    y_range = y_vals.max() - y_vals.min()
    plot_span = max(x_range, y_range, 1.0)
    scale = (plot_span * 0.3) / max(max_h, 1e-6)

    annotations = []
    for i, row in df_envelope.iterrows():
        px = x_vals.iloc[i]
        py = y_vals.iloc[i]
        dx = row[hx_col] * scale
        dy = row[hy_col] * scale
        tip_x = px + dx
        tip_y = py + dy

        annotations.append(dict(
            x=tip_x, y=tip_y, ax=px, ay=py,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5, arrowcolor=_COLOR_ARROW,
        ))

        if show_labels and row[res_col] > 1e-6:
            annotations.append(dict(
                x=tip_x, y=tip_y,
                text=f"<b>{row[res_col]:.1f}</b> {unit}",
                showarrow=False,
                font=dict(size=10, color=_COLOR_TEXT),
                xshift=10, yshift=10,
                bgcolor="rgba(255, 255, 255, 0.7)",
                bordercolor="rgba(148, 163, 184, 0.5)",
                borderpad=2,
            ))

    _add_pile_outlines(fig, x_vals, y_vals, pile_shape, pile_dim)

    layout = _base_layout(f"Envelope Lateral Vectors — {title_suffix}")
    layout["annotations"] = annotations

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

