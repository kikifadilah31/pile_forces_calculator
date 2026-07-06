"""
Matplotlib rendering of pile-group diagrams for the CLI / PNG output.

Mirrors the Plotly frontend visually (equal aspect, 0.5 m grid, gold centroid
cross, red = compression / blue = tension, emerald lateral vectors, zero-force
bubbles hidden). This module performs NO engineering calculation (Core 7); it
only draws DataFrames produced by `domain_engine` (already unit-converted).
"""

import matplotlib

matplotlib.use("Agg")  # headless backend — no display needed for file output

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator

from . import config

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _new_axes(title: str) -> tuple[Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=config.FIGSIZE)
    ax.set_title(title, fontsize=15, color=config.COLOR_TEXT, weight="bold", pad=14)
    ax.set_xlabel("X (m)", color=config.COLOR_TEXT)
    ax.set_ylabel("Y (m)", color=config.COLOR_TEXT)
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, which="both", color=config.COLOR_GRID, linewidth=0.6, alpha=0.8)
    ax.xaxis.set_major_locator(MultipleLocator(config.PLOT_GRID_DTICK))
    ax.yaxis.set_major_locator(MultipleLocator(config.PLOT_GRID_DTICK))
    ax.tick_params(colors=config.COLOR_TEXT, labelsize=8)
    ax.axhline(0, color="#94a3b8", linewidth=0.8, zorder=0)
    ax.axvline(0, color="#94a3b8", linewidth=0.8, zorder=0)
    return fig, ax


def _plot_centroid(ax: plt.Axes, centroid: tuple[float, float]) -> None:
    ax.scatter(
        [centroid[0]], [centroid[1]], marker="P", s=180,
        color=config.COLOR_CENTROID, edgecolors="#a16207", linewidths=1.2,
        zorder=6, label="Centroid",
    )


def _bubble_areas(abs_force: np.ndarray) -> np.ndarray:
    """Marker area (points^2) proportional to |force|; 0 for zero force."""
    max_force = abs_force.max() if abs_force.size and abs_force.max() > config.ZERO_TOL else 1.0
    areas = config.BUBBLE_MIN_AREA + (abs_force / max_force) * config.BUBBLE_MAX_EXTRA_AREA
    return np.where(abs_force <= config.ZERO_TOL, 0.0, areas)


def _vector_scale(x_vals: pd.Series, y_vals: pd.Series, max_h: float) -> float:
    """Reproduce the Plotly arrow scale: (plot_span * 0.3) / max_h."""
    x_range = float(x_vals.max() - x_vals.min())
    y_range = float(y_vals.max() - y_vals.min())
    plot_span = max(x_range, y_range, 1.0)
    return (plot_span * 0.3) / max(max_h, config.ZERO_TOL)


def _label_bubble(ax: plt.Axes, x: float, y: float, value: float) -> None:
    ax.annotate(
        f"{value:.1f}", (x, y), ha="center", va="center",
        fontsize=8, color=config.COLOR_TEXT, zorder=7,
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#94a3b8", alpha=0.75, lw=0.5),
    )


def save_figure(fig: Figure, path: str, dpi: int = config.OUTPUT_DPI) -> None:
    """Save a figure to PNG and release its memory."""
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Axial bubble plots
# ---------------------------------------------------------------------------

def _draw_axial(
    ax: plt.Axes,
    x_vals: pd.Series,
    y_vals: pd.Series,
    force_vals: pd.Series,
    show_labels: bool,
) -> None:
    abs_force = force_vals.abs().to_numpy(dtype=float)
    areas = _bubble_areas(abs_force)
    is_comp = force_vals.to_numpy(dtype=float) >= 0

    for mask, color, label in (
        (is_comp, config.COLOR_COMPRESSION, "Compression (+)"),
        (~is_comp, config.COLOR_TENSION, "Tension (−)"),
    ):
        visible = mask & (areas > 0)
        if visible.any():
            ax.scatter(
                x_vals[visible], y_vals[visible], s=areas[visible], c=color,
                edgecolors="white", linewidths=1.2, alpha=0.85, zorder=4, label=label,
            )

    if show_labels:
        for x, y, val in zip(x_vals, y_vals, force_vals, strict=True):
            _label_bubble(ax, x, y, val)


def plot_axial_bubbles(
    df_lc_subset: pd.DataFrame,
    centroid: tuple[float, float],
    show_labels: bool = True,
    unit: str = "kN",
) -> Figure:
    """Bubble plot of axial forces for a single load case."""
    lc_id = df_lc_subset["LC_ID"].iloc[0] if "LC_ID" in df_lc_subset.columns else "N/A"
    fig, ax = _new_axes(f"Axial Force Distribution — LC: {lc_id}  ({unit})")
    _draw_axial(ax, df_lc_subset["X"], df_lc_subset["Y"], df_lc_subset["Axial_Force"], show_labels)
    _plot_centroid(ax, centroid)
    ax.legend(loc="best", fontsize=8, framealpha=0.85)
    return fig


def plot_envelope_axial(
    df_envelope: pd.DataFrame,
    centroid: tuple[float, float],
    env_type: str = "Max",
    show_labels: bool = True,
    unit: str = "kN",
) -> Figure:
    """Bubble plot of envelope axial forces (env_type: 'Max' comp | 'Min' tens)."""
    col = "Max_Compression" if env_type == "Max" else "Max_Tension"
    title_suffix = "Max Compression" if env_type == "Max" else "Max Tension"
    fig, ax = _new_axes(f"Envelope Axial — {title_suffix}  ({unit})")
    _draw_axial(ax, df_envelope["X"], df_envelope["Y"], df_envelope[col], show_labels)
    _plot_centroid(ax, centroid)
    ax.legend(loc="best", fontsize=8, framealpha=0.85)
    return fig


# ---------------------------------------------------------------------------
# Lateral vector plots
# ---------------------------------------------------------------------------

def _draw_lateral(
    ax: plt.Axes,
    x_vals: pd.Series,
    y_vals: pd.Series,
    hx_vals: pd.Series,
    hy_vals: pd.Series,
    h_res_vals: pd.Series,
    pile_ids: pd.Series,
    show_labels: bool,
    unit: str,
) -> None:
    # Pile markers
    ax.scatter(
        x_vals, y_vals, marker="s", s=90, color=config.COLOR_PILE_MARKER,
        edgecolors="white", linewidths=1.2, zorder=4, label="Piles",
    )
    for x, y, pid in zip(x_vals, y_vals, pile_ids, strict=True):
        ax.annotate(str(pid), (x, y), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8, color=config.COLOR_TEXT)

    max_h = float(h_res_vals.max()) if len(h_res_vals) else 0.0
    scale = _vector_scale(x_vals, y_vals, max_h)

    for x, y, hx, hy, hres in zip(x_vals, y_vals, hx_vals, hy_vals, h_res_vals, strict=True):
        dx, dy = hx * scale, hy * scale
        if abs(dx) < config.ZERO_TOL and abs(dy) < config.ZERO_TOL:
            continue
        ax.annotate(
            "", xy=(x + dx, y + dy), xytext=(x, y),
            arrowprops=dict(arrowstyle="-|>", color=config.COLOR_ARROW, lw=2.2, shrinkA=0, shrinkB=0),
            zorder=5,
        )
        if show_labels and hres > config.ZERO_TOL:
            ax.annotate(
                f"{hres:.1f} {unit}", (x + dx, y + dy), textcoords="offset points",
                xytext=(8, 8), fontsize=8, color=config.COLOR_TEXT,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#94a3b8", alpha=0.75, lw=0.5),
            )


def plot_lateral_vectors(
    df_lc_subset: pd.DataFrame,
    centroid: tuple[float, float],
    show_labels: bool = True,
    unit: str = "kN",
) -> Figure:
    """Top-down lateral force vector plot for a single load case."""
    lc_id = df_lc_subset["LC_ID"].iloc[0] if "LC_ID" in df_lc_subset.columns else "N/A"
    fig, ax = _new_axes(f"Lateral Force Vectors — LC: {lc_id}  ({unit})")
    _draw_lateral(
        ax, df_lc_subset["X"], df_lc_subset["Y"], df_lc_subset["Hx"], df_lc_subset["Hy"],
        df_lc_subset["H_Resultant"], df_lc_subset["Pile_ID"], show_labels, unit,
    )
    _plot_centroid(ax, centroid)
    ax.legend(loc="best", fontsize=8, framealpha=0.85)
    return fig


def plot_envelope_lateral(
    df_envelope: pd.DataFrame,
    centroid: tuple[float, float],
    env_type: str = "Max",
    show_labels: bool = True,
    unit: str = "kN",
) -> Figure:
    """Envelope lateral vector plot (env_type: 'Max' | 'Min' resultant)."""
    res_col = "Max_Lateral" if env_type == "Max" else "Min_Lateral"
    hx_col = "Max_Lat_Hx" if env_type == "Max" else "Min_Lat_Hx"
    hy_col = "Max_Lat_Hy" if env_type == "Max" else "Min_Lat_Hy"
    title_suffix = "Max Resultant" if env_type == "Max" else "Min Resultant"

    fig, ax = _new_axes(f"Envelope Lateral Vectors — {title_suffix}  ({unit})")
    _draw_lateral(
        ax, df_envelope["X"], df_envelope["Y"], df_envelope[hx_col], df_envelope[hy_col],
        df_envelope[res_col], df_envelope["Pile_ID"], show_labels, unit,
    )
    _plot_centroid(ax, centroid)
    ax.legend(loc="best", fontsize=8, framealpha=0.85)
    return fig
