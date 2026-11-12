# Independent review of the native Sparkle improvement

Reviewed the implemented native exporter, source loader, reference adapter,
concrete execution and proof orchestration against the initial source snapshot
and `docs/improvement-plan.md`. The reviewer made no source edits.

No remaining important issue was found. The review confirmed:

- Expression semantics delegate to upstream `VerifyEmit.denote`; the private
  interpreter and operator lowering are removed.
- The record adapter retains every scalar coordinate and both arbitrary input
  memory functions. `Proof/Equivalence.lean` is unchanged from the initial demo,
  preserving the initialization and exact first-result scope.
- Both native source and metadata digests are checked before deriving bindings.
- Unsupported tactic/sorry bodies fail before elaboration. The reviewed
  file-writing injection creates no marker. Direct/qualified `sorryAx` is also
  rejected, with a regression for direct application.
- Header, options, declaration modifiers and empty deriving/termination wrappers
  are checked against the emitted format. This remains a format validator,
  rather than a sandbox for hostile Lean code.

The reviewer independently verified the 150 unchanged original-file hashes and
logs showing 20 demo tests and 46 original tests passing. The clean final entry
command was subsequently checked by the primary agent with exit status 0; its
complete log is [full-run.log](full-run.log). It proves all 458 field obligations,
both public theorems and rejects the XOR-1 native-output mutation. The public
axiom lists contain only `propext`, `Classical.choice` and `Quot.sound`.

A pinned Lean runtime crash on 128-field records was reduced to a minimal
example. Native storage now uses 64-field groups, exercised by the wide-register
smoke fixture. The initial proof run also exposed a shell-script edit race;
the final command was rerun with sources and entry script held unchanged.
