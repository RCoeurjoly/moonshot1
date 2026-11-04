# Lean artifact flow — checked 2026-11-04

`nix develop --command bash LeanFlow/run.sh` completed successfully.
[checked-run.log](checked-run.log) records the universal public theorem, its
standard axiom audit, and all four native control suites. Changed, well-typed
graph and SMT artifacts have concrete behavioral counterexamples and are
rejected by the fresh entry-point proof check. A false theorem is also rejected.

[Fresh review and fixes](review.md) records the parser regressions, their
resolution and one deferred test-helper minor. The three `negative-*.log`
files retain the intended kernel rejection diagnostics.

[artifacts.sha256](artifacts.sha256) identifies the exported graph and retained
hardware SMT. [regression-tests.log](regression-tests.log) records all 46
existing regression tests passing. [transfer-check.log](transfer-check.log)
records one fresh universal transfer check: 2m23s, 19,357,100 KiB peak RSS.
This is a resource observation, not an incremental proof-effort benchmark.

The retained temporal proof sources were restored with checked SHA-256 hashes
and rebuilt through Lake; all 436 transitions and the first-result theorem
passed. The final Nix command reused that dependency-checked library. The old
experiment's historical evidence and inconclusive effort measurements are
unchanged. Scope and external boundaries are in [the guide](../../LeanFlow/README.md).
