"""
Pile Forces Calculator — shared engineering core.

Distributes structural reaction forces (from Midas Civil) into individual
pile foundation forces using the rigid-pilecap / pile-group polar-inertia
method.

Two frontends share this package:
- Streamlit interactive app (`app.py`)
- Command-line interface (`pile_forces.cli`, entry point `pile-forces`)

All internal calculations use kN and meters (see `config.UNIT_SYSTEM`).
"""

__version__ = "0.2.0"
