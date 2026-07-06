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
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle
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


def _draw_pile_outline(
    ax: plt.Axes,
    x_vals: pd.Series,
    y_vals: pd.Series,
    pile_shape: str,
    pile_dim: float,
    label: str | None = "Pile (actual size)",
) -> None:
    """Draw each pile's true physical footprint as a dashed blue outline.

    `pile_dim` is the diameter (Circle) or side length (Square), in meters —
    drawn to true scale in data coordinates, distinct from the force-encoded
    bubble/marker drawn separately. Only the first patch carries a legend
    label so automatic legends don't repeat one entry per pile.
    """
    if pile_dim <= 0:
        return
    half = pile_dim / 2.0
    for i, (x, y) in enumerate(zip(x_vals, y_vals, strict=True)):
        patch_label = label if i == 0 else None
        if pile_shape == "Square":
            patch: Circle | Rectangle = Rectangle(
                (x - half, y - half), pile_dim, pile_dim,
                fill=False, edgecolor=config.COLOR_PILE_OUTLINE, linestyle="--",
                linewidth=1.4, zorder=5, label=patch_label,
            )
        else:
            patch = Circle(
                (x, y), half,
                fill=False, edgecolor=config.COLOR_PILE_OUTLINE, linestyle="--",
                linewidth=1.4, zorder=5, label=patch_label,
            )
        ax.add_patch(patch)


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


def _place_legend(ax: plt.Axes, handles: list | None = None) -> None:
    """Place the legend outside the plot (right side) so it never covers piles."""
    ax.legend(
        handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
        fontsize=8, framealpha=0.9, borderaxespad=0.0,
    )


def _finalize_axes(ax: plt.Axes) -> None:
    """Pad the view so the largest marker isn't clipped by the axes boundary.

    Scatter marker size (`s`) is in points^2 — a screen-space unit, not a
    data-space one — so autoscale (which only looks at x/y positions) can
    leave a large bubble straddling the axes edge, visually clipped.
    `Collection.get_window_extent()` does not reliably report marker-size
    extents for variable-size scatters (returns +/-inf in practice), so
    instead this reads each collection's actual `s` values directly, derives
    the largest marker's on-screen radius, and pads xlim/ylim by that radius
    converted to data units via the current pixels-per-data-unit scale.
    """
    max_area = 0.0
    for coll in ax.collections:
        sizes = coll.get_sizes()  # type: ignore[attr-defined]  # PathCollection (scatter), not generic Collection
        if len(sizes):
            max_area = max(max_area, float(sizes.max()))
    if max_area <= 0:
        return

    fig = ax.figure
    fig.canvas.draw()  # finalize the axes box position/size before measuring
    bbox = ax.get_window_extent()
    xlim, ylim = ax.get_xlim(), ax.get_ylim()

    radius_points = (max_area / np.pi) ** 0.5
    radius_px = radius_points * (fig.dpi / 72.0)
    pad_x = radius_px * (xlim[1] - xlim[0]) / bbox.width
    pad_y = radius_px * (ylim[1] - ylim[0]) / bbox.height

    ax.set_xlim(xlim[0] - pad_x, xlim[1] + pad_x)
    ax.set_ylim(ylim[0] - pad_y, ylim[1] + pad_y)


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
    marker: str = "o",
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
) -> tuple[bool, bool]:
    """Draw axial bubbles. Returns (has_compression, has_tension) for the legend."""
    abs_force = force_vals.abs().to_numpy(dtype=float)
    areas = _bubble_areas(abs_force)
    is_comp = force_vals.to_numpy(dtype=float) >= 0

    drawn = {"comp": False, "tens": False}
    for key, mask, color in (
        ("comp", is_comp, config.COLOR_COMPRESSION),
        ("tens", ~is_comp, config.COLOR_TENSION),
    ):
        visible = mask & (areas > 0)
        if visible.any():
            drawn[key] = True
            # No `label=` here: the legend swatch is built separately at a
            # fixed size (see _axial_legend_handles), decoupled from the
            # data-driven bubble size which would otherwise blow up the legend.
            ax.scatter(
                x_vals[visible], y_vals[visible], s=areas[visible], c=color,
                marker=marker, edgecolors="white", linewidths=1.2, alpha=0.85, zorder=4,
            )

    _draw_pile_outline(ax, x_vals, y_vals, pile_shape, pile_dim, label=None)

    if show_labels:
        for x, y, val in zip(x_vals, y_vals, force_vals, strict=True):
            _label_bubble(ax, x, y, val)

    return drawn["comp"], drawn["tens"]


def _axial_legend_handles(
    marker: str, has_compression: bool, has_tension: bool, show_pile_outline: bool = True,
) -> list[Line2D]:
    """Fixed-size legend swatches for axial bubble plots (independent of bubble data size)."""
    handles = []
    if has_compression:
        handles.append(Line2D(
            [0], [0], marker=marker, linestyle="None", markersize=config.LEGEND_MARKER_SIZE,
            markerfacecolor=config.COLOR_COMPRESSION, markeredgecolor="white", label="Compression (+)",
        ))
    if has_tension:
        handles.append(Line2D(
            [0], [0], marker=marker, linestyle="None", markersize=config.LEGEND_MARKER_SIZE,
            markerfacecolor=config.COLOR_TENSION, markeredgecolor="white", label="Tension (−)",
        ))
    handles.append(Line2D(
        [0], [0], marker="P", linestyle="None", markersize=config.LEGEND_MARKER_SIZE,
        markerfacecolor=config.COLOR_CENTROID, markeredgecolor="#a16207", label="Centroid",
    ))
    if show_pile_outline:
        handles.append(Line2D(
            [0], [0], color=config.COLOR_PILE_OUTLINE, linestyle="--", linewidth=1.4,
            label="Pile (actual size)",
        ))
    return handles


def plot_axial_bubbles(
    df_lc_subset: pd.DataFrame,
    centroid: tuple[float, float],
    show_labels: bool = True,
    unit: str = "kN",
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
) -> Figure:
    """Bubble plot of axial forces for a single load case."""
    lc_id = df_lc_subset["LC_ID"].iloc[0] if "LC_ID" in df_lc_subset.columns else "N/A"
    marker = config.PILE_SHAPE_MARKERS.get(pile_shape, "o")
    fig, ax = _new_axes(f"Axial Force Distribution — LC: {lc_id}  ({unit})")
    has_comp, has_tens = _draw_axial(
        ax, df_lc_subset["X"], df_lc_subset["Y"], df_lc_subset["Axial_Force"], show_labels,
        marker, pile_shape, pile_dim,
    )
    _plot_centroid(ax, centroid)
    _finalize_axes(ax)
    _place_legend(ax, _axial_legend_handles(marker, has_comp, has_tens, pile_dim > 0))
    return fig


def plot_envelope_axial(
    df_envelope: pd.DataFrame,
    centroid: tuple[float, float],
    env_type: str = "Max",
    show_labels: bool = True,
    unit: str = "kN",
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
) -> Figure:
    """Bubble plot of envelope axial forces (env_type: 'Max' comp | 'Min' tens)."""
    col = "Max_Compression" if env_type == "Max" else "Max_Tension"
    title_suffix = "Max Compression" if env_type == "Max" else "Max Tension"
    marker = config.PILE_SHAPE_MARKERS.get(pile_shape, "o")
    fig, ax = _new_axes(f"Envelope Axial — {title_suffix}  ({unit})")
    has_comp, has_tens = _draw_axial(
        ax, df_envelope["X"], df_envelope["Y"], df_envelope[col], show_labels, marker, pile_shape, pile_dim,
    )
    _plot_centroid(ax, centroid)
    _finalize_axes(ax)
    _place_legend(ax, _axial_legend_handles(marker, has_comp, has_tens, pile_dim > 0))
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
    marker: str = "s",
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
) -> None:
    # Pile markers
    ax.scatter(
        x_vals, y_vals, marker=marker, s=90, color=config.COLOR_PILE_MARKER,
        edgecolors="white", linewidths=1.2, zorder=4, label="Piles",
    )
    _draw_pile_outline(ax, x_vals, y_vals, pile_shape, pile_dim, label="Pile (actual size)")
    for x, y, pid in zip(x_vals, y_vals, pile_ids, strict=True):
        ax.annotate(str(pid), (x, y), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8, color=config.COLOR_TEXT)

    max_h = float(h_res_vals.max()) if len(h_res_vals) else 0.0
    scale = _vector_scale(x_vals, y_vals, max_h)

    tip_xs, tip_ys = [], []
    for x, y, hx, hy, hres in zip(x_vals, y_vals, hx_vals, hy_vals, h_res_vals, strict=True):
        dx, dy = hx * scale, hy * scale
        if abs(dx) < config.ZERO_TOL and abs(dy) < config.ZERO_TOL:
            continue
        tip_xs.append(x + dx)
        tip_ys.append(y + dy)
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

    if tip_xs:
        # ax.annotate() arrows do not participate in axes autoscaling, so
        # without this, arrow tips pointing away from the pile-marker extent
        # get silently clipped by the axes view. An invisible scatter forces
        # the tips into the autoscale computation.
        ax.scatter(tip_xs, tip_ys, s=0, alpha=0)


def plot_lateral_vectors(
    df_lc_subset: pd.DataFrame,
    centroid: tuple[float, float],
    show_labels: bool = True,
    unit: str = "kN",
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
) -> Figure:
    """Top-down lateral force vector plot for a single load case."""
    lc_id = df_lc_subset["LC_ID"].iloc[0] if "LC_ID" in df_lc_subset.columns else "N/A"
    marker = config.PILE_SHAPE_MARKERS.get(pile_shape, "o")
    fig, ax = _new_axes(f"Lateral Force Vectors — LC: {lc_id}  ({unit})")
    _draw_lateral(
        ax, df_lc_subset["X"], df_lc_subset["Y"], df_lc_subset["Hx"], df_lc_subset["Hy"],
        df_lc_subset["H_Resultant"], df_lc_subset["Pile_ID"], show_labels, unit, marker, pile_shape, pile_dim,
    )
    _plot_centroid(ax, centroid)
    _finalize_axes(ax)
    _place_legend(ax)
    return fig


def plot_envelope_lateral(
    df_envelope: pd.DataFrame,
    centroid: tuple[float, float],
    env_type: str = "Max",
    show_labels: bool = True,
    unit: str = "kN",
    pile_shape: str = "Circle",
    pile_dim: float = 0.0,
) -> Figure:
    """Envelope lateral vector plot (env_type: 'Max' | 'Min' resultant)."""
    res_col = "Max_Lateral" if env_type == "Max" else "Min_Lateral"
    hx_col = "Max_Lat_Hx" if env_type == "Max" else "Min_Lat_Hx"
    hy_col = "Max_Lat_Hy" if env_type == "Max" else "Min_Lat_Hy"
    title_suffix = "Max Resultant" if env_type == "Max" else "Min Resultant"
    marker = config.PILE_SHAPE_MARKERS.get(pile_shape, "o")

    fig, ax = _new_axes(f"Envelope Lateral Vectors — {title_suffix}  ({unit})")
    _draw_lateral(
        ax, df_envelope["X"], df_envelope["Y"], df_envelope[hx_col], df_envelope[hy_col],
        df_envelope[res_col], df_envelope["Pile_ID"], show_labels, unit, marker, pile_shape, pile_dim,
    )
    _plot_centroid(ax, centroid)
    _finalize_axes(ax)
    _place_legend(ax)
    return fig
