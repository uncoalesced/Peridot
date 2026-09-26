# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

# Peridot Core System Package.
#
# Intentionally empty. This package used to eagerly re-export CommandRouter and
# MedicalResearchModule, which meant `import core_system.anything` transitively
# executed all of config.py's import-time side effects (nvidia-smi subprocess,
# load_dotenv, directory creation, .env write) plus `import pynvml` -- before the
# requested module was even loaded. Both symbols are imported directly from their
# own modules by their real consumers (see core.py).
