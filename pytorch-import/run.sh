#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

unset LEAN_PATH LEAN_SRC_PATH PYTHONPATH
export LEAN_NUM_THREADS="${LEAN_NUM_THREADS:-2}"

mkdir -p build
# Materialize the exact Git revisions in lake-manifest.json, then obtain
# Mathlib's matching compiled dependencies. No existing checkout is needed.
if ! test -f .lake/cache-ready; then
  printf 'Fetching locked Lean dependencies and their Mathlib cache...\n'
  lake exe cache get
  touch .lake/cache-ready
fi
printf 'Building TorchLean import modules...\n'
lake -q build NN.Runtime.IR NN.Runtime.PyTorch.Export.TorchExport
lake env lean --run EmitExporter.lean
python3 export.py
lake env lean --run Import.lean
