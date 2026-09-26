# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

# ZAT-SCS tuning constants.
#
# Declared as a regular package (rather than relying on PEP 420 implicit
# namespace packages) so that setuptools' packages.find in pyproject.toml
# actually discovers it. Without __init__.py an installed wheel silently
# omitted this directory; the app only worked when run from the source root.
# Keep this module free of imports so importing a submodule stays cheap.
