#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x ../SparkleDemo/.lake/toolchains/lean-4.32.1-linux/bin/lake ||
      ! -d ../SparkleDemo/.lake/packages/sparkle || ! -d ../SparkleDemo/.lake/packages/LSpec ]]; then
  echo 'Prerequisite missing: install SparkleDemo toolchain/dependencies first (see its setup.sh).' >&2
  exit 1
fi
mkdir -p .lake
for directory in packages toolchains; do
  if [[ ! -e ".lake/$directory" ]]; then
    ln -s "../../SparkleDemo/.lake/$directory" ".lake/$directory"
  fi
done
printf 'SparkleOptDemo uses the pinned Sparkle toolchain/dependencies from SparkleDemo.\n'
