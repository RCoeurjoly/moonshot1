#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

usage() {
  cat <<'HELP'
Usage: bash SparkleDemo/run.sh [all|controls|proof]
  all       Fresh RTL import, seven trace controls and universal proof (default).
  controls  Fresh import and RTL/native-Lean/Sparkle-C comparisons.
  proof     Recheck the existing native artifact and universal proof.

Run setup.sh once first. Evidence and detailed logs are in SparkleDemo/build/.
HELP
}

if (( $# > 1 )); then usage >&2; exit 2; fi
stage="${1:-all}"
case "$stage" in
  -h|--help) usage; exit 0 ;;
  all|controls|proof) ;;
  *) usage >&2; exit 2 ;;
esac

if [[ -n "${SPARKLE_LEAN_BIN:-}" ]]; then
  export PATH="$SPARKLE_LEAN_BIN:$PATH"
elif [[ -x .lake/toolchains/lean-4.32.1-linux/bin/lake ]]; then
  export PATH="$PWD/.lake/toolchains/lean-4.32.1-linux/bin:$PATH"
fi

if [[ "$stage" == all || "$stage" == controls ]]; then python3 run.py; fi
if [[ "$stage" == all || "$stage" == proof ]]; then python3 prove.py; fi
