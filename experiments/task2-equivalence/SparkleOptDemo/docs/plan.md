# Sparkle opt-full implementation plan

> Execute inline using executing-plans; use TDD, independent final review and
> verification-before-completion. The user approved the preceding approach.

**Goal:** A separate Sparkle opt-full demo with universal proof and a checked
attempt at direct baseline/candidate equivalence.

**Architecture:** Reuse unchanged Sparkle expression reflection; independently
import frozen optimized RTL; derive candidate coordinates; check all transition
fields and compose its retained temporal theorem. Investigate direct native
state refinement as a distinct theorem.

**Tech stack:** Pinned Yosys 0.66, Sparkle revision 1614cee, Lean 4.32.1/4.35.
**Spec:** [design.md](design.md).

## Constraints and review focus

- Preserve all 202 existing source/report files recorded before this task.
- All new persistent changes under SparkleOptDemo; no commits or root config edits.
- Preserve arbitrary permitted initial registers, both input memories and start.
- Verify exact candidate/checkpoint identities; reject a no-op or schema mutation.
- Keep candidate proof modules distinct from baseline modules and artifacts.
- Fresh public checks and negative controls must prevent stale proof reuse.
- A direct theorem must state its state relation and dependency scope honestly.

## Tasks

1. [x] Freeze candidate/provenance pins; add failing tests for tampering, schema
   mapping and fresh normalization. Implement preparation helpers and isolated
   Lake setup using the already installed toolchain/dependencies.
2. [x] Import the candidate and execute all seven native-Lean/C/Verilator controls.
   Preserve explicit logs, hashes and cleared stale verdicts on failure.
3. [x] Implement candidate record adapter and proof modules, derive all 446
   obligations, check/assemble them and prove universal correctness/436 edges.
   Audit axioms and reject a fresh output mutation.
4. [x] Attempt direct native state refinement using the actual optimized register
   changes. Prove achievable direct statements and record limitations precisely.
5. [x] Record maintenance/timing/memory evidence, run all three regression suites,
   independently review, resolve findings, run the frozen final entry command,
   archive evidence and check preservation hashes.
