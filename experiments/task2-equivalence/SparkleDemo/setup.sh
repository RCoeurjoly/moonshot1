#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ "$(uname -s)-$(uname -m)" != Linux-x86_64 ]]; then
  printf 'Install Lean 4.32.1 with elan, then run lake update in SparkleDemo/.\n' >&2
  exit 1
fi

archive="$PWD/.lake/toolchains/lean-4.32.1-linux.tar.zst"
mkdir -p .lake/toolchains
if [[ ! -f "$archive" ]]; then
  curl -fL --retry 2 \
    https://github.com/leanprover/lean4/releases/download/v4.32.1/lean-4.32.1-linux.tar.zst \
    -o "$archive"
fi
printf '%s  %s\n' 57d5c062a6b4bae6fba511a1704aa124dff461c37d0fc94585637fbb7d951b50 "$archive" | sha256sum --check -
if [[ ! -x .lake/toolchains/lean-4.32.1-linux/bin/lake ]]; then
  tar --zstd -xf "$archive" -C .lake/toolchains
fi
export PATH="$PWD/.lake/toolchains/lean-4.32.1-linux/bin:$PATH"
lake update
