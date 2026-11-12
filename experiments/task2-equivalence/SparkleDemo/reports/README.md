# Retained verification evidence

Running `../run.sh` writes fresh results under `../build/`. Retained reports are
snapshots; their hashes describe the sources and artifacts from that run.

## Current native-model demo

The [native/](native/) snapshot validates the improvement that uses upstream
Sparkle reflection for operator semantics and executes the same native Lean
source in the controls and universal proof:

- [native/summary.json](native/summary.json): theorem names, 436 edges, 458 field
  obligations, seven controls, regression counts and original-file preservation.
- [native/universal-result.json](native/universal-result.json): every proof
  check, axiom audit, artifact identities and rejected native-output mutation.
- [native/control-result.json](native/control-result.json): fresh RTL import
  and original-RTL/native-Lean/Sparkle-C trace comparisons.
- [native/evidence.json.gz](native/evidence.json.gz): named source/text artifacts
  with hashes, including the actual native model, traces and proof logs.
- [native/full-run.log](native/full-run.log),
  [native/demo-tests.log](native/demo-tests.log),
  [native/original-tests.log](native/original-tests.log): successful commands.
- [native/review.md](native/review.md): independent review and resolved findings.

## Initial Sparkle demo

The files at this directory's root retain the initial validated demo, before
migration away from its private interpreter and operator lowering. They are
historical evidence, not a description of the current source path:

- [summary.json](summary.json), [universal-result.json](universal-result.json),
  [control-result.json](control-result.json): initial results.
- [evidence.json.gz](evidence.json.gz): initial generated artifacts and proof logs.
- [initial-sources.json.gz](initial-sources.json.gz): initial source snapshot,
  including the removed interpreter/lowering and the original design notes.
- [preservation.json](preservation.json), [original-tests.log](original-tests.log),
  [demo-tests.log](demo-tests.log): initial preservation and regression evidence.

Both versions establish a new complete transition equality before reusing the
retained temporal theorem. See [the guide](../README.md) and
[the design](../DESIGN.md) for the current contract and translation boundaries.
