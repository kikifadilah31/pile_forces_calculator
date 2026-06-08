"""
Typst-based PDF report generator for pile force analysis.

Uses the `typst` Python package to compile .typ markup into PDF.
Temporary files handled via Python's `tempfile` module.
"""

import os
import tempfile
from datetime import datetime

import pandas as pd

try:
    import typst
except ImportError:
    typst = None


def _escape_typst(text: str) -> str:
    """Escape special Typst characters in text strings."""
    replacements = {
        "#": "\\#",
        "$": "\\$",
        "@": "\\@",
        "_": "\\_",
        "~": "\\~",
    }
    for char, escaped in replacements.items():
        text = text.replace(char, escaped)
    return text


def _build_envelope_table(df_envelope: pd.DataFrame, unit: str) -> str:
    """Build a Typst table from the envelope DataFrame."""
    n_cols = len(df_envelope.columns)

    # Header row
    headers = []
    for col in df_envelope.columns:
        headers.append(f'  [*{_escape_typst(str(col))}*]')

    # Data rows
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
  fill: (col, row) => if row == 0 {{ rgb("1e293b") }} else if calc.odd(row) {{ rgb("f1f5f9") }} else {{ white }},
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
    plot_image_paths: list[str],
    unit: str = "kN",
) -> str:
    """Generate a Typst markup string for the analysis report.

    Parameters
    ----------
    df_envelope : Envelope DataFrame with governing load cases
    params : dict with all design parameters
    plot_image_paths : list of absolute paths to PNG plot images
    unit : output unit (kN or Ton)

    Returns
    -------
    Complete Typst document string
    """
    date_str = datetime.now().strftime("%d %B %Y")

    # Parameter summary
    pile_shape_text = params.get("pile_shape", "N/A")
    pile_dim_text = f"{params.get('pile_dim', 0):.3f} m"

    # Build image includes
    image_blocks = []
    for idx, img_path in enumerate(plot_image_paths):
        # Use forward slashes for Typst
        img_path_clean = img_path.replace("\\", "/")
        label = "Lateral Force Vectors" if idx == 0 else "Axial Force Distribution"
        image_blocks.append(f"""
#figure(
  image("{img_path_clean}", width: 100%),
  caption: [{label}],
)
""")

    images_section = "\n".join(image_blocks) if image_blocks else ""

    envelope_table = _build_envelope_table(df_envelope, unit)

    report = f"""#set document(
  title: "Pile Forces Analysis Report",
  author: "Pile Forces Calculator",
)

#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2.5cm, left: 2cm, right: 2cm),
  header: align(right, text(size: 8pt, fill: rgb("64748b"))[Pile Forces Calculator — Generated Report]),
  footer: align(center, text(size: 8pt, fill: rgb("64748b"))[Page #counter(page).display()]),
)

#set text(
  font: "Inter",
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
    #text(size: 22pt, weight: "bold", fill: white)[Pile Forces Analysis Report]
    #v(8pt)
    #text(size: 11pt, fill: rgb("94a3b8"))[Generated: {date_str}]
  ]
]

#v(16pt)

= Project Parameters

#table(
  columns: 2,
  align: (left, left),
  fill: (col, row) => if calc.odd(row) {{ rgb("f1f5f9") }} else {{ white }},
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

= Governing Load Cases (Envelope)

The following table shows the extreme forces for each pile and the corresponding governing load cases:

{envelope_table}

#v(24pt)
#align(center, text(size: 8pt, fill: rgb("94a3b8"))[
  — End of Report —
])
"""
    return report


def compile_report_to_pdf(
    typst_string: str,
    image_paths: list[str] | None = None,
) -> bytes | None:
    """Compile Typst markup into PDF bytes.

    Uses Python's tempfile for intermediate files.
    Returns PDF bytes or None if typst is not available.
    """
    if typst is None:
        return None

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Write main .typ file
        typ_path = os.path.join(tmp_dir, "report.typ")

        # If image paths are provided, copy or symlink them into temp dir
        # and update references in the typst string
        final_typst = typst_string
        if image_paths:
            for img_path in image_paths:
                if os.path.exists(img_path):
                    img_name = os.path.basename(img_path)
                    dest_path = os.path.join(tmp_dir, img_name)
                    # Copy image to temp directory
                    import shutil
                    shutil.copy2(img_path, dest_path)
                    # Update path in typst string to relative
                    img_path_fwd = img_path.replace("\\", "/")
                    final_typst = final_typst.replace(
                        f'image("{img_path_fwd}"',
                        f'image("{img_name}"',
                    )

        with open(typ_path, "w", encoding="utf-8") as f:
            f.write(final_typst)

        # Compile to PDF
        pdf_path = os.path.join(tmp_dir, "report.pdf")
        try:
            pdf_bytes = typst.compile(typ_path)
            return pdf_bytes
        except Exception as exc:
            raise RuntimeError(f"Typst compilation failed: {exc}") from exc
