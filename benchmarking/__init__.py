# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

# Peridot benchmarking suite.
#
# Run a benchmark as a module from the repository root, e.g.
#     python -m benchmarking.benchmark_decode_rate
#
# These modules previously each carried their own sys.path prologue -- five
# mutually incompatible dialects across 18 files -- and imported the shared
# helpers as a top-level `benchmark_utils`. Two of those dialects resolved to
# the wrong directory entirely, and mixing the flat and packaged spellings in
# one process loaded benchmark_utils twice under two names, yielding two
# distinct BenchmarkResult classes. Everything now imports
# `benchmarking.utils.benchmark_utils`.
