# Sparkle: the Yosys opt-full experiment

This separate demo imports the **same frozen `opt -full` candidate** as the
original experiment. The original xiangshan2Lean demo and Sparkle baseline stay
unchanged. All new sources, generated files and reports live here.

It checks two complementary results:

1. **Candidate correctness:** all 441 reference next-state fields and five
   outputs agree with the Sparkle import. Composition with the retained candidate
   temporal theorem establishes the universal Task 2 contract and exact first
   result at **436 rising edges**.
2. **Direct native refinement:** the optimized Sparkle model simulates the
   baseline Sparkle model for every cycle and every shared input stream, from
   states related by the explicit embedding. This proof uses neither retained
   circuit model nor its temporal theorem. Its transitive dependencies are audited.

## Run

From the experiment directory:

```sh
bash SparkleOptDemo/setup.sh
bash SparkleOptDemo/run.sh
python3 -m unittest discover -s SparkleOptDemo/tests -v
```

Setup reuses the pinned toolchain and Sparkle package already installed by
`SparkleDemo/setup.sh`. Install those prerequisites first if they are absent;
this setup never runs Lake updates in the existing demo. The Nix tools, original checkpoint and prepared
proof libraries are required; exact paths and hashes are in [pins.json](pins.json).
Sparkle exports with Lean 4.32.1; Lean 4.35 checks the emitted source and proofs.

Use `run.sh controls`, `run.sh candidate` or `run.sh direct` while iterating.
`run.sh proof` checks both proof stages against the current successful controls.
Every stage checks artifact identities, and failures clear its previous verdict.

## What is compared

The frontend reruns `opt -full` from the original physical checkpoint. Its RTL
must match the frozen candidate byte-for-byte, and its structural counts must
reproduce **6,754 → 5,738 registered bits** and **1,193 → 211 mux cells**.
These are normalized circuit statistics, not measured FPGA area or timing.

The candidate passes through the unchanged [upstream-reflecting exporter](NativeExport.lean).
Operator meanings remain supplied by Sparkle's `VerifyEmit.denote`; there is no
private operator interpreter. Native Lean, Sparkle C and original optimized RTL
are compared on all seven controls, including signed/overflow cases and **816**.

Two standard Yosys representation passes precede Sparkle parsing: `simplemap`
lowers reductions/logical gates and `splitnets -driver` avoids partial internal
wire writes. The experiment exposed width/partial-write problems in this pinned
Sparkle path; these passes let the unchanged reflector handle the circuit.
The controls and complete transition proof validate the resulting import.

## The direct state relation

The optimized native model has 439 scalar registers; the baseline has 451.
The embedding reconstructs a baseline state from an arbitrary optimized state:

| Registers | Embedding |
| --- | --- |
| 431 | Copy the corresponding value. |
| 8 | Expand a one-bit register into bit 0 or bit 4 of its original word. |
| 12 | Fill constant-propagated data registers with zero. |

Lean checks **all 451 updates and five outputs** under this relation. Induction
then establishes trace equality at every cycle. The concrete initial states
also agree under the embedding. The input streams range over the lifted port
interface, including the RAM-word inputs; constant RAM streams are covered.

This is a statement about **related states**. It does not equate arbitrary,
independently chosen raw states. The separate candidate correctness theorem
retains arbitrary permitted initial registers and the original fixed handshake.
Direct trace equivalence does not add a functional specification for backpressure
or repeated transactions.

## Read the proof

- [Proof/OptMain.lean](Proof/OptMain.lean): fresh candidate artifact check and
  public correctness/first-result theorems.
- [Proof/DirectHelpers.lean](Proof/DirectHelpers.lean): five generic mux/append
  identities and direct transition simplification.
- [Proof/DirectRuns.lean](Proof/DirectRuns.lean): the induction over every cycle.
- [Proof/DirectAudit.lean](Proof/DirectAudit.lean): inspect actual transitive proof
  dependencies and reject retained circuit references.
- [direct.py](direct.py): generate the proposed embedding, all field obligations,
  assembly and fresh public checker. See `Proof/build/generated/DirectMain.lean`
  after a run for the public direct theorem.

[SharedMath.lean](Proof/SharedMath.lean) contains pure bit-vector lemmas. Direct
proof modules load without either reference circuit model; a regression checks
this independently of the transitive proof audit. Both proof paths admit only
`propext`, `Classical.choice` and `Quot.sound`. Native output mutations on both
sides of the direct comparison must fail the fresh evaluator checks.

Fresh verdicts are `build/result.json`, `build/universal-result.json` and
`build/direct-result.json`. Complete logs and generated proof sources are in
`Proof/build/`. [reports/](reports/) retains the final run and maintenance/timing
measurements. RTL elaboration, normalization and Sparkle translation remain
external correctness boundaries; the Lean proofs do not verify those compilers.
