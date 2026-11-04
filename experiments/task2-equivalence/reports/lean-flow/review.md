# Fresh review and resolution

One fresh reviewer (`gpt-6-astra`) inspected `63e3f8b..289412b` read-only and
independently checked `Main.lean`. The frozen-artifact proof passed with the
standard axioms. No Critical issue was found.

Two Important parser issues were reproduced and fixed in one pass:

- Constructor, selector, operator and global-name shadowing was accepted.
  The review's actual-artifact mutation bound `pair` to `in2_st0`, yet produced
  the same parsed program. Twelve rejection cases failed before the fix and
  passed afterward. The parser now reserves supported syntax/operators and
  checks one global symbol table for constructors, selectors, the transfer
  function and the initial-state constant. Let bindings cannot shadow them.
- Unary `bvxor` was accepted as an identity. Its parser-level rejection test
  failed before the fix and passed afterward. XOR now requires at least two
  same-width operands; valid binary and multioperand execution controls pass.

The complete Nix workflow and the 46 existing regression tests were rerun after
the fixes. The adjacent logs record those results. No second review was used.

Minor, deferred: the negative-proof subprocess helper accepts any error rather
than requiring the specific kernel diagnostic. The actual retained checks
reported kernel type mismatches for `graph_checked`, `hardware_checked` and
the false equality. This does not weaken the universal proofs; it limits the
helper's ability to distinguish unrelated failures in future negative tests.

The reviewer set aside general SMT-LIB/model/protocol completeness, complete
script initialization satisfiability, external capture/compiler correctness,
byte sensitivity to irrelevant changes, manually constructed malformed ASTs,
and historical optimization/effort claims. The execution ledger records each
scope ruling and its cost.
