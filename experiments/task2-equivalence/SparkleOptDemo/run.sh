#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if (( $# > 1 )); then echo 'Supply at most one stage.' >&2; exit 2; fi
export PATH="${SPARKLE_LEAN_BIN:-$PWD/.lake/toolchains/lean-4.32.1-linux/bin}:$PATH"
mkdir -p build
candidate_proof() {
  /usr/bin/time -f '{"seconds":%e,"peak_process_rss_kib":%M}' -o build/candidate-proof.resource.json python3 prove.py
}
direct_proof() {
  /usr/bin/time -f '{"seconds":%e,"peak_process_rss_kib":%M}' -o build/direct-proof.resource.json python3 direct.py
}
case "${1:-all}" in
  controls) python3 run.py ;;
  candidate) candidate_proof ;;
  direct) direct_proof ;;
  proof) candidate_proof; direct_proof ;;
  all) python3 run.py; candidate_proof; direct_proof ;;
  -h|--help)
    echo 'Usage: bash SparkleOptDemo/run.sh [all|controls|candidate|direct|proof]'
    echo 'all: fresh opt-full RTL, controls, candidate correctness, direct native refinement.'
    echo 'Proof stages require a successful controls run with matching source hashes.' ;;
  *) echo 'Unknown stage; use --help.' >&2; exit 2 ;;
esac
