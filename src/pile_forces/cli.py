"""
Command-line interface — orchestrator only (template Core 7).

No business logic lives here: this module wires together io_utils,
validators, domain_engine, renderer, reporter, and provenance, then writes a
timestamped, self-documenting output folder.

Usage:
    pile-forces --piles piles.csv --load-cases load_cases.csv [--params p.json] [overrides...]
"""

import argparse
import datetime
import logging
import os
import sys
from multiprocessing import freeze_support

from . import __version__, config, domain_engine, io_utils, provenance, renderer, reporter, validators

logger = logging.getLogger("pile_forces")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pile-forces",
        description="Distribute structural reaction forces into individual pile foundation forces.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"pile-forces {__version__}")

    # --- Input paths (explicit, no auto-detection) ---
    g_in = parser.add_argument_group("input files (paths are required, no auto-detect)")
    g_in.add_argument("--piles", required=True, metavar="CSV", help="Pile coordinates CSV [Pile_ID, X, Y] (m).")
    g_in.add_argument("--load-cases", required=True, metavar="CSV", help="Load cases CSV [LC_ID, Fx, Fy, Fz, Mx, My, Mz] (kN, kN·m).")
    g_in.add_argument("--params", metavar="JSON", default=None, help="Optional design parameters JSON.")

    # --- Output ---
    g_out = parser.add_argument_group("output")
    g_out.add_argument("--output", metavar="DIR", default=config.OUTPUT_FOLDER, help="Parent folder for the timestamped run.")
    g_out.add_argument("--no-labels", action="store_true", help="Hide force-value text on plots.")
    g_out.add_argument("--no-report", action="store_true", help="Skip Typst PDF report generation.")
    g_out.add_argument("--report-title", default="Pile Forces Analysis Report", help="Title on the PDF report.")

    # --- Design parameter overrides (highest precedence; unset -> None) ---
    g_p = parser.add_argument_group("design parameter overrides (override --params / defaults)")
    g_p.add_argument("--pilecap-length", type=float, dest="pilecap_length")
    g_p.add_argument("--pilecap-width", type=float, dest="pilecap_width")
    g_p.add_argument("--pilecap-height", type=float, dest="pilecap_height")
    g_p.add_argument("--gamma-concrete", type=float, dest="gamma_concrete")
    g_p.add_argument("--soil-height", type=float, dest="soil_height")
    g_p.add_argument("--gamma-soil", type=float, dest="gamma_soil")
    g_p.add_argument("--pile-shape", choices=config.VALID_PILE_SHAPES, dest="pile_shape")
    g_p.add_argument("--pile-dim", type=float, dest="pile_dim")
    g_p.add_argument("--pile-length", type=float, dest="pile_length")
    g_p.add_argument("--gamma-pile", type=float, dest="gamma_pile")
    g_p.add_argument("--centroid", choices=config.VALID_CENTROID_MODES, dest="centroid_mode")
    g_p.add_argument("--xc", type=float, dest="x_centroid")
    g_p.add_argument("--yc", type=float, dest="y_centroid")
    g_p.add_argument("--unit", choices=config.VALID_OUTPUT_UNITS, dest="output_unit")

    return parser


def _overrides_from_args(args: argparse.Namespace) -> dict:
    """Collect only the design-parameter flags from parsed args."""
    return {key: getattr(args, key) for key in config.DEFAULT_PARAMS if getattr(args, key, None) is not None}


# ---------------------------------------------------------------------------
# Output folder + logging setup
# ---------------------------------------------------------------------------

def make_run_dir(parent: str) -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(parent, f"{config.OUTPUT_PREFIX}_{stamp}")
    os.makedirs(os.path.join(run_dir, "plots"), exist_ok=True)
    return run_dir


def _configure_logging(run_dir: str) -> logging.FileHandler:
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    file_handler = logging.FileHandler(os.path.join(run_dir, "run.log"), encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    return file_handler


# ---------------------------------------------------------------------------
# Rendering + reporting
# ---------------------------------------------------------------------------

def _render_all_plots(df_master_disp, df_env_disp, centroid, run_dir, show_labels, unit, pile_shape, pile_dim):
    plots_dir = os.path.join(run_dir, "plots")
    plot_paths: list[tuple[str, str]] = []

    for lc_id in df_master_disp["LC_ID"].unique():
        subset = df_master_disp[df_master_disp["LC_ID"] == lc_id]

        fig_lat = renderer.plot_lateral_vectors(subset, centroid, show_labels, unit, pile_shape, pile_dim)
        p_lat = os.path.join(plots_dir, f"lateral_{lc_id}.png")
        renderer.save_figure(fig_lat, p_lat)
        plot_paths.append((p_lat, f"Lateral Force Vectors — LC: {lc_id}"))

        fig_ax = renderer.plot_axial_bubbles(subset, centroid, show_labels, unit, pile_shape, pile_dim)
        p_ax = os.path.join(plots_dir, f"axial_{lc_id}.png")
        renderer.save_figure(fig_ax, p_ax)
        plot_paths.append((p_ax, f"Axial Force Distribution — LC: {lc_id}"))
        logger.info("Rendered plots for LC %s", lc_id)

    envelope_specs = [
        (renderer.plot_envelope_axial, "Max", "env_max_compression.png", "Envelope — Max Axial Compression"),
        (renderer.plot_envelope_axial, "Min", "env_max_tension.png", "Envelope — Max Axial Tension"),
        (renderer.plot_envelope_lateral, "Max", "env_max_lateral.png", "Envelope — Max Lateral Resultant"),
        (renderer.plot_envelope_lateral, "Min", "env_min_lateral.png", "Envelope — Min Lateral Resultant"),
    ]
    for fn, env_type, fname, caption in envelope_specs:
        fig = fn(
            df_env_disp, centroid, env_type=env_type, show_labels=show_labels,
            unit=unit, pile_shape=pile_shape, pile_dim=pile_dim,
        )
        path = os.path.join(plots_dir, fname)
        renderer.save_figure(fig, path)
        plot_paths.append((path, caption))
    logger.info("Rendered %d envelope plots", len(envelope_specs))

    return plot_paths


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    run_dir = make_run_dir(args.output)
    file_handler = _configure_logging(run_dir)
    try:
        logger.info("pile-forces %s — run dir: %s", __version__, run_dir)

        # --- Resolve params (config -> JSON -> CLI overrides) ---
        params = io_utils.load_params(args.params, _overrides_from_args(args))
        params = validators.validate_params(params)
        unit = params["output_unit"]
        show_labels = not args.no_labels
        logger.info("Parameters resolved (unit=%s, centroid=%s).", unit, params["centroid_mode"])

        # --- Load + validate input (fail-fast) ---
        df_piles = validators.validate_piles_df(io_utils.load_piles_csv(args.piles))
        df_lc = validators.validate_load_cases_df(io_utils.load_load_cases_csv(args.load_cases))
        logger.info("Loaded %d piles and %d load cases.", len(df_piles), len(df_lc))

        # --- Compute ---
        df_master = domain_engine.build_master_output(df_piles, df_lc, params)
        df_envelope = domain_engine.build_envelope(df_master)
        logger.info("Computed %d pile x LC combinations; envelope for %d piles.", len(df_master), len(df_envelope))

        if params["centroid_mode"] == "Auto":
            centroid = (float(df_piles["X"].mean()), float(df_piles["Y"].mean()))
        else:
            centroid = (params["x_centroid"], params["y_centroid"])

        df_master_disp = io_utils.convert_units(df_master, unit)
        df_env_disp = io_utils.convert_units(df_envelope, unit)

        # --- Provenance ---
        input_files = [p for p in (args.piles, args.load_cases, args.params) if p]
        provenance.write_manifest(run_dir, __version__, input_files, params, vars(args))
        logger.info("Wrote run_manifest.json")

        # --- CSV outputs ---
        df_master_disp.to_csv(os.path.join(run_dir, "master_output.csv"), index=False)
        df_env_disp.to_csv(os.path.join(run_dir, "envelope.csv"), index=False)
        logger.info("Wrote master_output.csv and envelope.csv")

        # --- Plots ---
        plot_paths = _render_all_plots(
            df_master_disp, df_env_disp, centroid, run_dir, show_labels, unit,
            params["pile_shape"], params["pile_dim"],
        )

        # --- Summary + report ---
        reporter.write_summary_md(run_dir, df_env_disp, params, unit, __version__)
        logger.info("Wrote SUMMARY.md")

        if args.no_report:
            logger.info("PDF report skipped (--no-report).")
        else:
            typst_src = reporter.generate_typst_report(
                df_env_disp, params, plot_paths, unit=unit, report_title=args.report_title,
            )
            pdf_bytes = reporter.compile_report_to_pdf(typst_src, plot_paths)
            if pdf_bytes is None:
                logger.warning("Package `typst` not installed — PDF report skipped. Install with `pip install typst`.")
            else:
                pdf_path = os.path.join(run_dir, "Pile_Analysis_Report.pdf")
                with open(pdf_path, "wb") as fh:
                    fh.write(pdf_bytes)
                logger.info("Wrote Pile_Analysis_Report.pdf")

        logger.info("Done. Output: %s", run_dir)
        return 0
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 2
    finally:
        file_handler.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args)


def entry_point() -> None:
    freeze_support()
    sys.exit(main())


if __name__ == "__main__":
    entry_point()
