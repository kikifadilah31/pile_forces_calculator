"""
Typst-based PDF report generator + auditable Markdown summary.

Uses the `typst` Python package to compile .typ markup into PDF. Temporary
files are handled via Python's `tempfile` module. The report embeds the
matplotlib PNGs produced by `renderer` and the governing-load-case envelope.
"""

import os
import shutil
import tempfile
from datetime import datetime

import pandas as pd

try:
    import typst
except ImportError:  # pragma: no cover — optional dependency
    typst = None  # type: ignore[assignment]


def _escape_typst(text: str) -> str:
    """Escape special Typst characters in text strings."""
    replacements = {
        "#": "\\#", "$": "\\$", "@": "\\@", "_": "\\_", "~": "\\~",
    }
    for char, escaped in replacements.items():
        text = text.replace(char, escaped)
    return text


def _build_envelope_table(df_envelope: pd.DataFrame) -> str:
    """Build a Typst table from the envelope DataFrame."""
    n_cols = len(df_envelope.columns)

    headers = [f'  [#text(white)[*{_escape_typst(str(col))}*]]' for col in df_envelope.columns]

    data_rows = []
    for _, row in df_envelope.iterrows():
        for col in df_envelope.columns:
            val = row[col]
            if isinstance(val, float):
                data_rows.append(f"  [{val:.2f}]")
            else:
                data_rows.append(f"  [{_escape_typst(str(val))}]")

    table_content = ",\n".join(headers + data_rows)

    return f"""#table(
  columns: {n_cols},
  align: center + horizon,
  fill: (_, row) => if row == 0 {{ rgb("1e293b") }} else if calc.odd(row) {{ rgb("f1f5f9") }} else {{ white }},
  stroke: 0.5pt + rgb("94a3b8"),
  inset: 8pt,
{table_content},
)"""


def _build_methodology_section() -> str:
    """Build the methodology text for the report."""
    return r"""
== Methodology

The pile forces are calculated using static mechanics principles based on pile group polar inertia distribution:

=== Axial Force Distribution
For each pile $i$ under a load case:

$ P_("axial",i) = P_("total") / n - (M_(x,"act") dot y_i) / (sum y_i^2) + (M_(y,"act") dot x_i) / (sum x_i^2) + W_("pile") $

Where $P_("total") = F_(z,"act") + W_("pilecap") + W_("soil")$

=== Lateral & Torsion Distribution
$ H_(x,i) = F_(x,"act") / n - (M_(z,"act") dot y_i) / I_("polar") $

$ H_(y,i) = F_(y,"act") / n + (M_(z,"act") dot x_i) / I_("polar") $

$ H_("resultant",i) = sqrt(H_(x,i)^2 + H_(y,i)^2) $

Where $I_("polar") = sum x_i^2 + sum y_i^2$
"""


def generate_typst_report(
    df_envelope: pd.DataFrame,
    params: dict,
    plot_image_paths: list[tuple[str, str]],
    unit: str = "kN",
    report_title: str = "Pile Forces Analysis Report",
) -> str:
    """Generate a Typst markup string for the analysis report.

    Parameters
    ----------
    df_envelope : envelope DataFrame with governing load cases
    params : dict with all design parameters
    plot_image_paths : list of (absolute_path, caption) for PNG plot images
    unit : output unit (kN or Ton)
    report_title : title on the first page
    """
    date_str = datetime.now().strftime("%d %B %Y")

    pile_shape_text = params.get("pile_shape", "N/A")
    pile_dim_text = f"{params.get('pile_dim', 0):.3f} m"

    # Optional project metadata lines in the title block (omit if blank)
    meta_pairs = [
        ("Project", params.get("project_name", "")),
        ("Engineer", params.get("engineer", "")),
        ("Revision", params.get("revision", "")),
    ]
    meta_block = "".join(
        f'\n    #v(4pt)\n    #text(size: 11pt, fill: rgb("cbd5e1"))[{label}: {_escape_typst(str(val))}]'
        for label, val in meta_pairs if str(val).strip()
    )

    # Optional capacity verdict
    capacity_note = ""
    if params.get("check_capacity") and "Status" in df_envelope.columns:
        n_bad = int((df_envelope["Status"] == "INADEQUATE").sum())
        verdict = "ALL PILES OK" if n_bad == 0 else f"{n_bad} PILE(S) INADEQUATE (DCR > 1.0)"
        color = "16a34a" if n_bad == 0 else "dc2626"
        capacity_note = (
            f'\n#v(8pt)\n#block(width: 100%, fill: rgb("{color}"), radius: 6pt, inset: 10pt)['
            f'#text(fill: white, weight: "bold")[Capacity Check: {verdict}]]\n'
        )

    image_blocks = []
    for img_path, label in plot_image_paths:
        img_name = os.path.basename(img_path)
        image_blocks.append(f"""
#figure(
  image("{img_name}", width: 100%),
  caption: [{_escape_typst(label)}],
)
""")
    images_section = "\n".join(image_blocks) if image_blocks else ""

    envelope_table = _build_envelope_table(df_envelope)

    report = f"""#set document(
  title: "{_escape_typst(report_title)}",
  author: "Pile Forces Calculator",
)

#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2.5cm, left: 2cm, right: 2cm),
  header: align(right, text(size: 8pt, fill: rgb("64748b"))[Pile Forces Calculator — Generated Report]),
  footer: context align(center, text(size: 8pt, fill: rgb("64748b"))[Page #counter(page).display()]),
)

#set text(
  size: 10pt,
  fill: rgb("1e293b"),
)

#set heading(numbering: "1.1")

// --- Title Block ---
#align(center)[
  #block(
    width: 100%,
    fill: rgb("1e293b"),
    radius: 8pt,
    inset: 24pt,
  )[
    #text(size: 22pt, weight: "bold", fill: white)[{_escape_typst(report_title)}]
    #v(8pt)
    #text(size: 11pt, fill: rgb("94a3b8"))[Generated: {date_str}]{meta_block}
  ]
]
{capacity_note}
#v(16pt)

= Project Parameters

#table(
  columns: 2,
  align: (left, left),
  fill: (_, row) => if calc.odd(row) {{ rgb("f1f5f9") }} else {{ white }},
  stroke: 0.5pt + rgb("94a3b8"),
  inset: 8pt,
  [*Parameter*], [*Value*],
  [Pilecap Dimensions], [{params.get("pilecap_length", 0):.2f} × {params.get("pilecap_width", 0):.2f} × {params.get("pilecap_height", 0):.2f} m],
  [Concrete Unit Weight], [{params.get("gamma_concrete", 0):.1f} kN/m³],
  [Soil Fill Height], [{params.get("soil_height", 0):.2f} m],
  [Soil Unit Weight], [{params.get("gamma_soil", 0):.1f} kN/m³],
  [Pile Shape], [{pile_shape_text}],
  [Pile Dimension], [{pile_dim_text}],
  [Pile Length], [{params.get("pile_length", 0):.2f} m],
  [Pile Unit Weight], [{params.get("gamma_pile", 0):.1f} kN/m³],
  [Output Unit], [{unit}],
)

{_build_methodology_section()}

= Visualizations

{images_section}

#page(flipped: true)[
= Governing Load Cases (Envelope)

The following table shows the extreme forces for each pile and the corresponding governing load cases:

#text(size: 8pt)[
{envelope_table}
]

#v(24pt)
#align(center, text(size: 8pt, fill: rgb("94a3b8"))[
  — End of Report —
])
]
"""
    return report


def compile_report_to_pdf(
    typst_string: str,
    image_paths: list[tuple[str, str]] | None = None,
) -> bytes | None:
    """Compile Typst markup into PDF bytes.

    Returns PDF bytes, or None if the `typst` package is not installed.
    """
    if typst is None:
        return None

    with tempfile.TemporaryDirectory() as tmp_dir:
        if image_paths:
            for img_path, _ in image_paths:
                if os.path.exists(img_path):
                    shutil.copy2(img_path, os.path.join(tmp_dir, os.path.basename(img_path)))

        typ_path = os.path.join(tmp_dir, "report.typ")
        with open(typ_path, "w", encoding="utf-8") as fh:
            fh.write(typst_string)

        try:
            return typst.compile(typ_path)
        except Exception as exc:  # noqa: BLE001 — re-raise with context
            raise RuntimeError(f"Typst compilation failed: {exc}") from exc


def write_summary_md(
    out_dir: str,
    df_envelope: pd.DataFrame,
    params: dict,
    unit: str,
    tool_version: str,
) -> str:
    """Write an auditable SUMMARY.md (Core 4/8). Returns the file path.

    Shows governing values per pile and the intermediate self-weights so the
    result can be traced, not just a pass/fail.
    """
    from . import math_engine  # local import to avoid cycle at module load

    w_pilecap = math_engine.calc_pilecap_weight(
        params["pilecap_length"], params["pilecap_width"],
        params["pilecap_height"], params["gamma_concrete"],
    )
    w_soil = math_engine.calc_soil_weight(
        params["pilecap_length"], params["pilecap_width"],
        params["soil_height"], params["gamma_soil"],
    )
    pile_area = math_engine.calc_pile_area(params["pile_shape"], params["pile_dim"])
    w_pile = math_engine.calc_pile_weight(pile_area, params["pile_length"], params["gamma_pile"])

    lines = [
        "# Pile Forces Analysis — SUMMARY",
        "",
        f"- Tool version: `pile-forces {tool_version}`",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Output unit: **{unit}**",
    ]
    for label, key in (("Project", "project_name"), ("Engineer", "engineer"), ("Revision", "revision")):
        if str(params.get(key, "")).strip():
            lines.append(f"- {label}: {params[key]}")
    if params.get("check_capacity") and "Status" in df_envelope.columns:
        n_bad = int((df_envelope["Status"] == "INADEQUATE").sum())
        verdict = "ALL PILES OK" if n_bad == 0 else f"{n_bad} pile(s) INADEQUATE (DCR > 1.0)"
        lines.append(f"- **Capacity check: {verdict}**")
    lines += [
        "",
        "## Intermediate Values (kN)",
        "",
        f"- W_pilecap = {w_pilecap:.3f} kN",
        f"- W_soil = {w_soil:.3f} kN",
        f"- Pile area = {pile_area:.4f} m² ({params['pile_shape']}, dim {params['pile_dim']} m)",
        f"- W_pile (per pile) = {w_pile:.3f} kN",
        "",
        "## Governing Forces per Pile",
        "",
        "| Pile | Max Compression | Gov LC | Max Tension | Gov LC | Max Lateral | Gov LC |",
        "|------|----------------:|:------:|------------:|:------:|------------:|:------:|",
    ]
    for _, r in df_envelope.iterrows():
        lines.append(
            f"| {r['Pile_ID']} | {r['Max_Compression']:.2f} | {r['LC_Max_Comp']} "
            f"| {r['Max_Tension']:.2f} | {r['LC_Max_Tens']} "
            f"| {r['Max_Lateral']:.2f} | {r['LC_Max_Lat']} |"
        )

    lines += [
        "",
        "## Method",
        "",
        "Rigid-pilecap elastic distribution (pile-group polar inertia). See the "
        "PDF report / PRD for full formulas. All forces converted to the output "
        f"unit ({unit}); internal computation in kN·m.",
        "",
    ]

    path = os.path.join(out_dir, "SUMMARY.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path
