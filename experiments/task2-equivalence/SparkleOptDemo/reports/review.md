# Independent reviews

The proof reviewer worked only in `/tmp`, independently checking the difficult
candidate field batches and representative direct fields. Kernel AC normalization
and a single commutative simplification pass resolved the candidate differences.
Finite mux/append identities resolved the direct relation. The reviewer checked
complete first32 direct fields,12 later fields and all5 outputs, plus all8
expanded bits, all12 zero-filled fields and initial-state compatibility. All
successful axiom audits used only the permitted standard axioms.

A separate whole-code reviewer found no mathematical issue with the explicit
embedding, induction, fresh evaluator/initial-state checks or dependency audit.
The review identified three implementation issues, all resolved:

1. Proof-only mode verified only the required native artifacts. It now verifies
   every recorded control artifact. A changed-C-trace regression failed before
   the fix and passes afterward.
2. Shared frontend commands bypassed timing and process-group cleanup. They now
   use this demo's executor, with restoration in `finally`; the reviewer checked
   restoration even on failure.
3. Setup recovery could run Lake updates in the existing demo. It now reports
   missing prerequisites and never invokes that setup or updates its manifest.

Pure math was factored into SharedMath so direct modules load without either
reference circuit model. An import-independence regression failed before this
change and passes afterward. The dependency audit additionally traverses actual
proof definitions and rejects retained Task2/LeanFlow circuit references.

The reviewer rechecked all fixes and all202 original source/report hashes and
reported no remaining important issue. The primary agent performs the final full
pipeline run with code/configuration held fixed; its evidence is retained in
[full-run.log](full-run.log) and the proof manifests.
