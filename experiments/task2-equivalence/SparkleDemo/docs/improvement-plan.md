# Native Sparkle semantics and a readable demo

The user approved improving the separate Sparkle demo after identifying the
private IR-to-Lean semantics layer as unwanted. Keep all work in SparkleDemo;
preserve the original demo and every current universal guarantee.

Use Sparkle's pinned `Tools.SVParser.VerifyEmit.denote` for expression semantics
and `Verify.extractModel` for register discovery. The convenience `verilog!`
entry point does not support the circuit's signed comparison. Its stricter
reflection interface supports it and rejects unsupported expressions.

Export readable Lean source with named input/state/output records. The demo's
exporter supplies declaration layout and reference substitution; it must not
contain its own operator-to-Lean interpretation. A reference adapter handles
only ports, state coordinates and the immutable RAM view. Retain a fresh
artifact check and the existing transaction theorem only after checking all
453 state fields and five outputs.

The two Lean versions remain explicit while the retained proof library uses
4.35 and Sparkle uses 4.32.1. The same upstream-reflected Lean source must check
in both. Do not hide this compatibility boundary or claim the RTL parser is
verified.

## Implementation

1. [x] Add a failing native-export smoke test, then implement an exporter that
   delegates every expression to upstream Sparkle. Compile its emitted code
   under both Lean versions; check overflow, signed comparison and reset.
2. [x] Replace Proof/Generate's private operator lowering with a declaration
   loader and record-only reference adapter. Recheck every transition field,
   the public universal theorem, exact 436-edge result and mutated artifact.
3. [x] Improve the entry point, stage names, progress messages, named constants
   and guide. Keep a short reading path and move implementation details into
   focused documentation. Improve validation where evidence identifies a gap.
4. [x] Run both regression suites and the complete documented command. Audit
   axioms and identities; retain updated reports separately from the first
   validated snapshot. Obtain independent code review and resolve important
   findings.

## Acceptance

- No private operator semantics in the proof import path.
- All seven original-RTL/native-Sparkle/C controls and 458 field proofs pass.
- Universal claims retain arbitrary permitted initial state and input RAMs.
- Only propext, Classical.choice and Quot.sound occur in public proofs.
- Changed imports and stale reports fail closed.
- All pre-existing tracked original-demo files remain byte-identical.

## Verified result

The final `bash SparkleDemo/run.sh` exited 0. All seven controls, all 458 field
obligations, both public theorems and native-output mutation rejection passed.
Twenty demo tests and 46 original tests pass. The public axiom lists retain only
the three standard axioms; all 150 original tracked files are byte-identical.
Independent review has no remaining important findings. Retained evidence is
under [reports/native/](../reports/native/); the initial source snapshot and
reports remain available for comparison.
