# Task 2 Equivalence and Proof Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for sequential implementation, or superpowers:subagent-driven-development if that execution method is explicitly selected. Steps use checkbox tracking.

**Goal:** Prove the existing Task 2 int32 dot product equivalent to its compiled implementation, then establish correctness after one substantive pipeline change with less incremental proof work.

**Architecture:** Reuse the already frozen, Nix-reproducible Task 2 in /home/roland/LLM2FPGA, including its model, toolchain and generated RTL. Import the source and hardware models into one Lean environment, prove both against a shared word-level contract, and reuse the resulting infrastructure for a Yosys-optimized candidate. Compare with EQY using the same two implementations.

**Tech Stack:** Nix; the existing pinned PyTorch/Torch-MLIR/MLIR/CIRCT route; Yosys; xiangshan2Lean; Lean 4.35.0; TorchLean; EQY/SBY and recorded solver backends; Python standard-library orchestration/tests; Verilator for correspondence controls.

**Spec:** [Task 2 equivalence design](../specs/2026-11-03-task2-equivalence-design.md). Read it before executing this plan.

## Global Constraints

- Both vectors have 16 signed int32 elements, represented by their complete 32-bit words.
- The reference reduction uses multiplication and addition modulo 2^32.
- Quantify over all pairs of input vectors, including overflow cases.
- Verify one transaction from the initialized kernel state.
- Follow the existing testbench environment: four rising clock edges of reset, start held until the input handshake accepts it, out0_ready and in2_st0_ready held high, and in2_st0_done_valid held low.
- The observed result is the data associated with the first accepted in2_st0_valid event.
- Prove that the initial-state relation is inhabited for every pair of input vectors.
- Use Lean 4.35.0, with TorchLean's pinned dependency closure.
- Write implementation and generated artifacts under /home/roland/moonshot1/experiments/task2-equivalence.
- Read the original repositories without modifying them.
- Reuse Task 2's existing Nix baseline; do not create another source snapshot, freeze procedure or compiler setup.

## Review Focus

1. Negative and overflowing inputs must retain full int32 word semantics; cover them in Task 2.
2. Reset or source initializers must not make symbolic input initialization impossible; prove existence and test preservation in Tasks 3–4.
3. An output token or ready signal must not be mistaken for accepted result data; cover event selection in Tasks 3–4.
4. Changed reference graphs, stale generated definitions, and no-op optimization runs must not receive a successful milestone verdict; cover identity and structure checks in Tasks 1, 2, 5 and 6.
5. Timeout/unsupported runs and warm-cache speedups must not be reported as proofs or reduced engineering effort; cover classification and measurement in Task 6.

## File Structure

All paths below are relative to experiments/task2-equivalence unless explicitly marked otherwise.

| File | Responsibility |
|---|---|
| flake.nix and flake.lock | Verification tools and experiment commands; reuse Task 2's existing Nix derivations and toolchain. |
| lean-toolchain, lakefile.lean and lake-manifest.json | One compatible Lean/dependency closure. |
| contract.json | Dimensions, dtype, numerical and protocol contract, selected transformation, and benchmark budget. |
| scripts/import_reference.py | Produce TorchLean interchange data from the existing Nix-pinned model and environment. |
| scripts/run.py | Stage CLI, provenance, process measurements and result classification. |
| Task2/WordDot.lean | Word types, dot-product definition, reusable arithmetic lemmas. |
| Task2/Source.lean | Strict semantics of the actual imported integer graph and source_agrees theorem. |
| Task2/Hardware.lean | Shared Device, protocol, initialization and first-result definitions; pure hardware-runtime adapter. |
| Task2/Baseline.lean | Baseline-specific state mapping, invariant, completion bound and correctness theorem. |
| Task2/Candidate.lean | Candidate-specific facts and correctness proof using shared infrastructure. |
| Task2/Audit.lean | Public theorem imports and dependency audit. |
| formal/candidate.eqy | Exact baseline/candidate comparison and solver strategy. |
| tests/test_experiment.py | Interoperability, negative controls, identity and outcome tests. |
| README.md and reports/comparison.json | Reproduction commands and measured result with its proof/trust scope. |

Keep build/ generated and ignored. Generated pure Lean source and hardware definitions live under build/generated/Task2/Imported/. Preserve their bytes and hashes in a reviewable artifact bundle. The existing Task 2 repository remains the baseline provider.

## Shared Interfaces

The stage CLI is run from the experiment directory:

~~~sh
nix develop path:. --command python3 scripts/run.py attach --task2 /home/roland/LLM2FPGA --out build
nix develop path:. --command python3 scripts/run.py reference --out build
nix develop path:. --command python3 scripts/run.py hardware --design baseline --out build
nix develop path:. --command python3 scripts/run.py check --design baseline --out build
nix develop path:. --command python3 scripts/run.py variant --out build
nix develop path:. --command python3 scripts/run.py hardware --design candidate --out build
nix develop path:. --command python3 scripts/run.py check --design candidate --out build
nix develop path:. --command python3 scripts/run.py compare --repeats 3 --timeout 600 --out build
nix develop path:. --command python3 scripts/run.py report --out build
~~~

After attach creates build/manifest.json from the existing Task 2 derivations, each stage verifies prerequisite identities and writes a stage result containing status, commands, tool versions, elapsed time, peak RSS and artifact hashes. The manifest names the existing model/source derivations, derived Lean reference representation, and each implementation separately; extending it cannot replace the original baseline identities.

Use these result statuses: prepared, passed_control, proved, disproved, unsupported, timeout, failed, and no_change. A subprocess exit code alone cannot select proved or disproved.

The Lean-facing interfaces are defined locally rather than assumed to exist upstream:

~~~lean
namespace Task2
abbrev Word := BitVec 32
abbrev Words := Fin 16 → Word

def dot32 (a b : Words) : Word
def sourceEval (a b : Words) : Except String Word

structure Device where
  State : Type
  initial : Words → Words → State → Prop
  step : State → State
  result : State → Option Word

def run (d : Device) (s : d.State) (cycles : Nat) : d.State
def FirstResult (d : Device) (s : d.State) (n : Nat) (expected : Word) : Prop
def Implements (d : Device) (f : Words → Words → Except String Word) : Prop
end Task2
~~~

Device.step includes the fixed testbench driver and clock-phase bookkeeping.
Device.result is some data only on an accepted payload event.
FirstResult requires the expected event at cycle n and no earlier accepted payload.
Implements includes initial-state existence for every a,b and a single finite uniform bound C such that every permitted initial state produces a first result v by C and f a b = .ok v. A definition with only chosen zero-filled state or conditional output agreement is insufficient.

Generated devices are Task2.Imported.baseline and Task2.Imported.candidate.
Proofs establish source_agrees, baseline_correct and candidate_correct. The latter two use sourceEval as their reference, with the shared dot32 theorem as an intermediate lemma.

~~~lean
theorem source_agrees (a b : Task2.Words) :
    Task2.sourceEval a b = .ok (Task2.dot32 a b)
theorem baseline_correct :
    Task2.Implements Task2.Imported.baseline Task2.sourceEval
theorem candidate_correct :
    Task2.Implements Task2.Imported.candidate Task2.sourceEval
~~~

The Python tests use unittest.TestCase in tests/test_experiment.py. At each task, run the tests implemented so far with:

~~~sh
nix develop path:. --command python3 -m unittest discover -s tests -p test_experiment.py -v
~~~

Expected: all current tests pass. Each task's new assertions must first fail on the missing behavior. Proof checks use the relevant Lake module, for example:

~~~sh
nix develop path:. --command lake build Task2.Source
nix develop path:. --command lake build Task2.Baseline
nix develop path:. --command lake build Task2.Candidate Task2.Audit
~~~

Expected: successful proof compilation followed by the declared axiom audit, with the exact generated-definition hashes retained. These checks are planned execution commands, not results already obtained.

### Task 1: Attach the existing Nix baseline to the verification experiment

**Files:** Create flake.nix, flake.lock, contract.json, scripts/run.py, tests/test_experiment.py and .gitignore.

**Consumes:** The existing frozen Task 2 Nix setup in /home/roland/LLM2FPGA: matmul-sv-sim and its model, compiler, RTL and toolchain dependencies.

**Produces:** build/manifest.json pointing to the existing source, compiler intermediates, baseline sources.f/RTL and pinned tools, plus the retained baseline simulation result.

- [x] Add test_attached_task2_interface and test_stale_reference_is_rejected. Assert two int32 [16] inputs, scalar int32 output, identities taken from the existing Nix derivations, and rejection when referenced artifacts do not match those identities.
- [x] Run the named tests with Python unittest and confirm failure before implementing the attachment/identity checks.
- [x] Inspect the existing matmul-sv-sim dependency graph with nix derivation show --recursive. Locate its matmul-sv, Torch MLIR, model/adapter source paths and pinned Python/compiler tools. Do not assume a public matmul-sv flake attribute exists, and do not add a snapshot or exposure patch.
- [x] Implement attach to record those existing artifacts and the simulation PASS result. Reuse realized Nix outputs; if an output is absent, realize its existing derivation through Nix without changing the baseline or creating result symlinks in the original repository. The experiment flake adds verification dependencies only.
- [x] Run the named tests and attach command; confirm the recorded paths, source interface and artifact identities, then commit this task's files.

### Task 2: Import the reference graph and establish exact integer semantics

**Files:** Create lean-toolchain, lakefile.lean, lake-manifest.json, scripts/import_reference.py, Task2/WordDot.lean and Task2/Source.lean. Extend scripts/run.py and tests/test_experiment.py.

**Consumes:** The existing Nix-pinned model/adapter, compiler-input provenance and PyTorch environment recorded in Task 1.

**Produces:** Pure imported Lean graph definitions, sourceEval, dot32 and source_agrees.

- [x] Pin TorchLean f37cbc5aca8e79943b0ef0e3d3499ca9719d7c2b and its lockfile under Lean 4.35.0. Reuse its FloatLib dependency. Build focused imports rather than the entire example suite.
- [x] Produce the interchange graph needed by TorchLean from the existing pinned model and Python environment. Reuse a saved export when present; otherwise derive the import representation with the existing adapter/export flags. Relate its operation, shapes and dtypes to the existing compiler input. Keep the original Nix derivations and their inputs unchanged.
- [x] Attempt the actual upstream typed import and numerical evaluation. Retain the diagnosed behavior: the inspected reference interpreter does not provide general integer arithmetic. Integer representation/shape support alone cannot pass this task.
- [x] Add test_reference_word_parity for zeros, negative values, INT32_MIN/MAX, product overflow, accumulation overflow and cancellation. Serialize inputs/outputs by complete words. Add test_reference_rejects_changed_operation for a mutated graph operation.

  Required expected words include: all-zero vectors -> 0x00000000; a[0]=-2 and b[0]=3 -> 0xfffffffa; a[0]=INT32_MIN and b[0]=-1 -> 0x80000000; a[0]=INT32_MAX and b[0]=2 -> 0xfffffffe; products INT32_MAX and 1 in the first two positions -> 0x80000000. All unspecified elements are zero. Compare both pinned PyTorch execution and the imported evaluator with these expectations.
- [x] Implement the smallest local evaluator over the imported, checked Program for its actual input and integer-dot/matmul nodes. Define rank-1 int32 contraction with modular multiply/add. Reject every unsupported node, dtype or shape; do not fabricate a general arithmetic dictionary.
- [x] If the imported graph uses an unsupported dot spelling, add a narrow importer rule retaining source-node provenance and identical rank/dtype semantics. Keep the existing model and compiler input unchanged. (Not needed: actual capture uses aten.matmul.default.)
- [x] Prove source_agrees for all Words inputs by reducing the imported graph semantics to dot32. The graph must be represented by pure Lean definitions, not an IO-only test of JSON interpretation. Record the trusted PyTorch/operator/import connection separately.
- [x] Run the reference tests and reference command, then build Task2.Source with Lake. Confirm the universal theorem and parity controls before committing.

### Task 3: Import the actual baseline hardware and define the protocol relation

**Files:** Create Task2/Hardware.lean. Extend flake.nix, scripts/run.py and tests/test_experiment.py. Generate the imported hardware module and include the pinned runtime in the artifact bundle.

**Consumes:** Baseline RTL/file list/RTLIL and word inputs from Tasks 1–2.

**Produces:** Task2.Imported.baseline, Device semantics, explicit memory/state map, and aligned concrete traces.

- [x] Add test_payload_event_selection and test_symbolic_ram_survives_reset. Include a trace where out0_valid and payload validity differ, and two distinct RAM contents under the real reset sequence.
- [x] Pin xiangshan2Lean a1299b564831e571b9b80f816219ae06c91db342. Reuse the retained FunctionalIR import procedure, including JSON initialization constraints and clock normalization. Record the exact frontend and all passes.
- [x] Preserve word operations and memories. Port/check the small hardware runtime under Lean 4.35.0; regenerate and recompile all definitions rather than importing Lean 4.19.0 objects. Compile with no unsupported cells or substituted black boxes.
- [x] Map the two input memories and the accepted payload signal using the elaborated design. Do not rely only on the testbench's generated memory names; check widths, depths and provenance.
- [x] Define Device, run, FirstResult and Implements as specified above. Carry fixed driver/reset state inside Device.step and retain actual RAM initialization constraints.
- [x] Replay matching reset/start/result traces against RTL simulation for the Task 2 vector and negative/overflow controls, checking the sampling convention explicitly. These are correspondence controls, not the final proof.
- [x] Run hardware --design baseline and the named tests, compile the imported model, then commit the runtime adapter and mapping.

### Task 4: Prove baseline correctness and completion

**Files:** Create Task2/Baseline.lean and Task2/Audit.lean. Extend tests/test_experiment.py and scripts/run.py.

**Consumes:** source_agrees, shared Device contract and the actual imported baseline transition function.

**Produces:** baseline_correct, its concrete completion bound and an auditable proof bundle.

- [x] State baseline_correct before proving it and run its build to expose the missing obligations. Do not use sorry, admit, a solver-success axiom, or a precondition assuming the desired result.
- [x] Prove initial-state existence for every a,b, preservation of input memory through reset, and entry into the computation phase under the fixed driver.
- [x] Define/prove the controller invariant relating index, loaded operands, accumulator and completed products to a prefix of dot32. Relate the true implementation registers/memories to that invariant.
- [x] Derive a uniform finite bound from the imported control behavior, including handshake phases; prove FirstResult and compose with source_agrees. Do not turn the 10000-cycle simulation timeout into an assumption.
- [x] Add test_corrupt_payload_has_counterexample: XOR the observed payload bit zero in an explicitly labeled test-only mutant, replay a concrete input and retain its mismatch witness. Add test_mismatched_artifact_cannot_reuse_verdict.
- [x] Implement check --design baseline to bind the theorem and complete generated-definition hashes, run the proof build and transitive axiom audit, and distinguish correspondence controls from the theorem.
- [x] Record baseline proof-construction effort separately from dependency/setup/import effort. Run all baseline checks, inspect the public theorem type and assumptions, and commit.

### Task 5: Make one substantive pipeline change and reuse the proof

**Files:** Create Task2/Candidate.lean and formal/candidate.eqy. Extend flake.nix, scripts/run.py and tests/test_experiment.py.

**Consumes:** The existing Nix reference, baseline normalized implementation, baseline_correct and shared proof infrastructure.

**Produces:** Compiler-generated candidate RTL, structural change evidence, candidate_correct, and an EQY comparison result.

- [x] Add test_variant_noop_is_not_success. A transformed serialization with identical normalized logic/state must produce no_change, not an optimization or proof-reuse success.
- [x] Define the shared normalization checkpoint before the treatment. Generate the candidate by applying Yosys opt -full at that checkpoint and writing RTL2; record pass arguments and compare normalized cell/state/connectivity structure with generated names removed.
- [x] Require a substantive change. If opt -full is a no-op, retain that experiment result and revise the selected single transformation before claiming this milestone; do not manufacture a source change or count renaming as success.
- [x] Run the same hardware import on RTL2 and verify the unchanged external contract. Reuse WordDot, Source, Hardware and design-independent invariant lemmas unchanged; place candidate-specific facts and the final theorem in Candidate.
- [x] Prove candidate_correct against sourceEval. Factor an imported-hardware refinement lemma if that is simpler, but prove it in Lean before composing with baseline_correct. Record which definitions, invariant clauses and proofs needed edits.
- [x] Configure EQY with baseline as gold and candidate as gate, the same startup/input-memory contract, and defined accepted observations. Verify shared symbolic payloads are neither unconstrained independently nor tied to the sample vector. Use a supported memory-capable strategy and record its engine. Preserve unknown-state semantics; no arbitrary setundef-to-zero workaround.

  The comparison harness must connect both designs to the same symbolic initial RAM words and preserve their source-defined initial bits. Retain its relation to the Device.initial contract. If the selected EQY flow cannot express that contract, classify the comparison as unsupported and keep Lean as the primary result; a default comparison of independently unknown RAMs cannot substitute for it.
- [x] Check the candidate proof and dependency audit. Run EQY and retain its evidence/status, and verify the corrupted-payload control produces a concrete mismatch. Commit the transformation, proofs and exact comparison setup.

### Task 6: Measure reuse and publish the reproducible result

**Files:** Extend scripts/run.py, tests/test_experiment.py and Task2/Audit.lean. Create README.md and reports/comparison.json.

**Consumes:** The attached Nix baseline, both theorem bundles, EQY configuration/results, stage measurements and effort records.

**Produces:** Reproduction instructions, a machine-readable comparison and a scoped milestone verdict.

- [x] Add test_timeout_is_inconclusive, test_solver_failure_is_not_counterexample and test_missing_effort_prevents_less_work_claim. Assert the result schema retains artifact identities and trust scope.
- [x] Implement compare with three warm repetitions and a 600-second per-run limit, recording median wall time, peak RSS, cache state and backend. Measure Lean replay for each design and EQY separately; retain first-run/setup costs outside warm medians.
- [x] Record engineering events by actor (human/agent), phase, active duration, intervention and changed obligations. Keep unavailable token/cost data null. Compare baseline proof construction with incremental candidate proof work, with one-time provisioning excluded from that comparison.
- [x] Implement report so success requires both Lean proofs, non-vacuous initialization, derived completion, fixed artifact identities, an actual implementation change, and measured lower incremental proof work. If effort does not decrease, report that result without changing the criterion. EQY supports an additional refinement conclusion only when it proves the configured claim.
- [x] Run the complete CLI sequence and unittest suite from the frozen experiment environment. Replay the proofs from retained generated definitions with search artifacts removed. Verify an exact manifest match for every published verdict.
- [x] Write the result and reproduction instructions, including the current trust boundaries and the separate integer-semantic extension. Commit only this experiment's files and the measured report.

## Handoff and Later Work

This plan stops at a single Task 2 transaction and one pipeline transformation. TinyStories, variable latency, backpressure, repeated transactions, and automated optimization are subsequent plans.

Execute the tasks sequentially because their artifact identities, semantics and proof interfaces depend on each other. The main uncertainty is how much invariant discovery the actual Handshake controller requires; report its cost rather than replacing the implementation with a handwritten dot-product circuit.

Planning review: each acceptance condition maps to Tasks 1–6; all five Review Focus conditions have named checks; shared CLI, module and theorem names are consistent. The original source repositories were inspected during planning. Execution evidence is retained under experiments/task2-equivalence/reports; completed task checkboxes below describe the implemented result.

