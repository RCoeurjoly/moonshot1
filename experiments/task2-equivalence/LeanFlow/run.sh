#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export LEAN_NUM_THREADS="${LEAN_NUM_THREADS:-2}"

# Python stops at JSON. Every import, interpretation and proof below is Lean.
python3 LeanFlow/export.py
lake -q build LeanFlow.Graph LeanFlow.SMT
lake env lean --run LeanFlow/Prepare.lean
lake env lean --run LeanFlow/GenerateBridge.lean
# Keep the retained-library rebuild separate from the large transfer proof.
printf 'Checking retained Task 2 transaction proof...\n'
lake -q build Task2.Baseline
printf 'Checking interpreter equivalence...\n'
lake -q build LeanFlow.Equivalence
lake env lean --run LeanFlow/GraphTests.lean
lake env lean --run LeanFlow/SMTTests.lean
lake env lean --run LeanFlow/TransferTests.lean

# Direct invocation is intentional: re-read both raw artifacts even when Lake
# has cached the proof modules. The theorem compares them with checked data.
lake env lean LeanFlow/Main.lean
lake env lean --run LeanFlow/NegativeTests.lean
