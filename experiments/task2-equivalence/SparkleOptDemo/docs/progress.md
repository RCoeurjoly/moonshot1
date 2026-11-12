# Execution ledger — plan: SparkleOptDemo/docs/plan.md

- User authorized both candidate proof and subsequent direct-equivalence attempt.
- Existing feature branch task2-equivalence; user requested separate repo demo.
  Ruling: use a new directory in the current checkout; do not create worktrees
  or modify read-only git metadata. No commits are required for this task.
- Recorded 202 existing source/report hashes in /tmp/task2-before-sparkle-opt.json.
- Preflight: baseline reference has 453 fields, candidate 441; both input RAMs
  remain indices 30/31. Candidate output word is 370 (baseline 380).
- Candidate removes/merges several buffer data registers. Widths of surviving
  same-name reference fields are unchanged. State correspondence must be derived.
- Plan task 2 consumes task 1's verified RTL; task 3 consumes task 2's native
  source/schema; task 4 consumes both native models and task 3's setup. All
  generated proof module names will carry Opt prefix to avoid cache collisions.

- Task 1: preparation tests observed RED, then GREEN (7 tests). Fresh opt-full
  reproduces the exact candidate RTL hash and both physical-statistics snapshots.
- Ruling: use standard Yosys simplemap for reduction/logical cells. Upstream
  reflection otherwise produces mismatched 32-bit zero comparisons. No local
  operator lowering or upstream source modification was introduced.
- Found native Lean 36-edge completion while Sparkle C and RTL completed at 436.
  Register traces isolated first divergence at edge 6: buffer24 data1 bit 4.
  Upstream IR's partial-wire write shifted a one-bit value by 4 before slicing
  bit 4; C promoted it, strict BitVec semantics truncated it. Ruling: split
  internal nets at driver boundaries in Yosys, preserving all register widths.
  A concrete partial-write fixture failed before this fix and passed afterward.
- One candidate register has a different alias (output word aliases ldData1).
  Mapping now uses exact normalized Yosys net-bit identity; every proposed
  coordinate will still be checked universally by Lean.

- All seven candidate controls now pass (RTL = Sparkle C = native Lean, 436 edges).
- New candidate bridge checked all 441 state and 5 output fields. Two generic
  finite BitVec lemmas (two-bit reduction truth and padded one-bit concat)
  plus kernel AC normalization and single-pass commutative simplification
  handle optimizer differences. Repeated simp_all with AC laws was too slow;
  independent /tmp review identified the supported acNf option and verified
  the formerly failing batches with only the permitted three axioms.
- Public entry caught a parser/elaborator command collision with the baseline
  adapter (both used adapt_native_reference). Ruling: new command is named
  adapt_opt_reference, leaving baseline unchanged. Rechecking public artifact.
- Direct embedding covers all optimized registers: 431 copies, 8 expansions at
  bit0/4, 12 baseline buffer14/15/17 data fields fixed0. Reviewer proved all20
  special fields and native initialState compatibility; remaining451-field
  refinement requires finite mux/append identities, not a new operator model.
- Direct public goal: all cycles for arbitrary optimized state and arbitrary
  shared input stream, with baseline state related by embed. This is not an
  equality claim for arbitrary unrelated raw states. Actual theorem dependency
  closure must exclude the old candidate model and theorem.
- Preparation now kills its full process group on timeout and records that
  status. All9 Python boundary tests pass, including timeout regression.

- Candidate public theorem and exact first_result now check with exactly the
  permitted three axioms after isolating its adapter command. Fresh native
  output XOR-1 mutation is rejected at artifact_checked.
- Direct refinement now checks all 451 baseline register-update fields and5
  outputs (456 checks). DirectAssemble proves nextState_agrees, outputs_agree
  and initial_agrees; DirectRuns proves arbitrary-length run/trace equivalence.
- Direct proof uses five elementary mux/append lemmas plus the two generic
  candidate normalization lemmas. Every field and run audit has allowed axioms.
  Independent review checked complete first32 fields,12 representative later
  fields, all5 outputs, all8 bit expansions and all12 eliminated zero fields.
- Direct public checker reloads both actual source files, wraps records into
  the checked model types and verifies evaluator AND initial-state identities.
  Final transitive dependency audit and dual output mutation tests are pending.

- Direct fresh evaluator and initial-state checks passed. Transitive audit
  inspected11330 declarations for trace equivalence and found no Task2/LeanFlow
  circuit/theorem dependency. Both baseline and candidate XOR-1 imports were
  rejected by their respective fresh artifact equality.
- Ruling: factor pure bit-vector lemmas into SharedMath so DirectHelpers also
  loads without either reference circuit model, rather than merely avoiding
  them in proof terms. The new import-independence regression failed before
  factoring and passed afterward; all12 current Python tests pass.
- Finalization pending: independent whole-code review, baseline bridge timing,
  fresh complete candidate+direct execution after factoring, all regression
  suites, retained evidence and202-file preservation audit.

- Final independent review found one important provenance gap: proof-only mode
  checked only three control artifacts. A changed C-trace regression failed
  before the fix and passes when every recorded artifact is verified. Logs,
  resource records and staged candidate RTL are also included in the manifest.
- Resolved both minor review notes: shared frontend calls now use this demo's
  process-group/time/RSS executor (restored afterward); setup now reports missing
  baseline prerequisites instead of running Lake updates in the existing demo.
- Original regression46/46 and Sparkle baseline20/20 pass. Existing202 source/
  report hashes remain unchanged. Candidate/direct full rerun and benchmarks
  will use frozen final sources after review fixes.

- Final frozen `bash SparkleOptDemo/run.sh` exited0: exact opt-full regeneration,
  seven three-way controls, candidate441+5 universal field checks, public436-edge
  theorem, direct451+5 field checks/all-cycle induction, fresh both-model/init
  checks, transitive dependency audits and all three output mutations passed.
- Baseline bridge observation168.02s/4386908KiB; optimized bridge286.94s/4087260KiB;
  direct native refinement130.70s/2485208KiB. Single warm observations, not an
  engineering-effort or general speed benchmark.
- All79 tests pass (46 original +20 Sparkle baseline +13 optimized); all202
  pre-existing source/report hashes match and all30 frozen code/config hashes
  remained fixed during the final command. Reports retained under reports/.
