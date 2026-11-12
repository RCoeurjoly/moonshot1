# Native Sparkle model: architecture and boundaries

The public contract and run commands are in [README.md](README.md). This document
explains the translation and proof interfaces that matter when extending it.

## 1. Import the actual RTL

[run.py](run.py) verifies the frozen source hashes in [pins.json](pins.json), then
runs Slang/Yosys afresh. It elaborates hierarchy, flattens the circuit and checks
that the two input RAMs are read-only 16×32 memories with one read port. It also
checks that registers use the positive edge of the single `clock` input.

The frontend uses `memory_map -keepdc` and exposes the 32 input words as ports.
Concrete runs hold them constant. The proof supplies arbitrary memory functions,
so unspecified input words are never silently replaced with zero. The writable
output memory remains register state. The ANSI-header adapter uses Yosys's JSON
widths and changes only port declarations, preserving the emitted circuit body.
Explicit unknown literals cause rejection.

Sparkle's pinned `Tools.SVParser.Lower.parseAndLowerHierarchical` parses the fresh
normalized RTL. [Import.lean](Import.lean) exports diagnostic IR, Sparkle C and
round-trip Verilog. The round-trip file is a diagnostic, not a proof oracle.

## 2. Use upstream expression semantics

[ExportTask2.lean](ExportTask2.lean) calls [NativeExport.lean](NativeExport.lean).
The exporter uses these upstream interfaces:

- `Tools.SVParser.Verify.extractModel` discovers registers and their next values.
- `Tools.SVParser.VerifyEmit.widthTable` and `widthOf` inspect native widths.
- **`Tools.SVParser.VerifyEmit.denote` supplies every expression's Lean term.**
- `Sparkle.Backend.CSim.scheduleEvalBody` orders the combinational assignments.

The local code substitutes named references and lays out records/declarations;
it has no operator dispatch or private arithmetic/shift implementation. The
result imports only `Std`, uses standard `BitVec` operations, and contains:

```lean
Task2RTL.Inputs       -- Named RTL ports, including the 32 input words.
Task2RTL.State        -- Named physical registers.
Task2RTL.Outputs      -- The five RTL outputs.
Task2RTL.evaluate    -- Inputs → State → { outputs, nextState }.
```

Wire functions preserve sharing in the expression graph. State storage uses
64-field groups with inherited named projections. This avoids the pinned Lean
runtime's large-constructor problem while preserving the readable public API.
The smoke test exercises more than 64 registers.

Unknown widths, scalar widths outside 1–64, width mismatches, identifier
sanitization collisions, unsupported statements, wrong clocks and combinational
cycles are rejected. Register widths are checked against actual declarations;
the upstream register-discovery fallback width is not accepted implicitly.

Sparkle's convenience `verilog!` entry point uses a different, incomplete
reflection path that does not handle this circuit's signed comparator. The
stricter upstream `VerifyEmit.denote` interface supports the imported graph.
This demo therefore uses that interface directly.

## 3. Run one native Lean model in both environments

Sparkle is pinned at `1614cee83ac586ca9a0626cd4af13bfef7347c3a`, using Lean 4.32.1.
The retained Task 2 proof library requires Lean 4.35.0. The exporter emits ordinary
Lean source at `build/native/Task2RTL.lean`; that exact file is compiled in both
environments. There is no serialization into another private expression language.

[NativeTraces.lean](NativeTraces.lean) executes this model for seven controls.
Sparkle C and fresh original-RTL Verilator provide independent trace checks.
Trace comparison checks binary handshakes, consecutive cycles, every handshake
value, the accepted payload and exactly one completion on the last row. Every
control must have 436 rows. Unaccepted payloads are outside the observable contract.
`initialState` is a concrete simulation seed; it does not restrict the theorem.

Override binary directories with `SPARKLE_LEAN_BIN` and
`SPARKLE_PROOF_LEAN_BIN`. The two exact Lean versions are checked. No root Lake
configuration or toolchain file is changed. The default Nix tool paths are
workspace-specific; changing machines requires supplying the same tool closures
and reference library.

## 4. Establish a new complete transition proof

[Proof/ReferenceAdapter.lean](Proof/ReferenceAdapter.lean) copies records between
the named native state and the existing reference coordinates. It also presents
the two immutable RAMs as 32 arbitrary input words. It does not interpret circuit
expressions. A proposed bijection is generated from names and widths, then checked
through proofs of all 453 next-state fields and five outputs, for arbitrary raw
state and inputs. The two extra reference fields are the unchanged RAM functions.

The new equality is composed with the retained temporal proof, yielding the
public equivalence and exact first-result theorems. See [Proof/README.md](Proof/README.md).
The library's temporal argument is reused after this full equality; it is not a
new derivation of the controller schedule from scratch.

[Proof/NativeArtifact.lean](Proof/NativeArtifact.lean) reparses native source in a
fresh namespace. It permits the generated records, pure definitions, `noinline`
definitions and three exact local options. Other imports, commands, declaration
modifiers, tactic bodies, holes and root-qualified names are rejected before
elaboration. `Main.lean` loads the current
artifact again; kernel-checked equality prevents a changed artifact inheriting
cached field proofs. The XOR-1 native-output mutation must fail at this equality.
The loader is a format validator, not a sandbox for hostile Lean source.

## Trust and scope

Lean checks the mathematical proofs and final dependencies. Public theorem axiom
audits admit only `propext`, `Classical.choice` and `Quot.sound`, rejecting
`sorryAx`, native-evaluation axioms and external solver verdicts.

The declared translation boundaries are Slang/Yosys elaboration/normalization,
the validated read-only-memory lift, Sparkle parsing/lowering and upstream
reflection, and the local declaration/record layout. These translators are not
formally proved correct here. Concrete agreement adds evidence about translation;
it does not certify compiler correctness or prove the C backend correct.

The theorem covers one baseline transaction with the original fixed handshake.
It does not cover arbitrary backpressure, repeated transactions, the optimized
candidate, timing closure or physical FPGA measurements. Initial proof reports
are retained as historical snapshots; fresh verdicts are cleared before reruns.
