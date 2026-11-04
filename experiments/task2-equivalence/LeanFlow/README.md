# PyTorch → Lean ← hardware SMT

Start with [Main.lean](Main.lean). Its two import commands **read and parse the
actual JSON and SMT files in Lean**. The theorem proves that their observable
Task 2 computations agree for all input words and permitted initial registers.

From `experiments/task2-equivalence`, using the existing pinned Nix environment:

```sh
nix develop --command bash LeanFlow/run.sh
```

The frozen Task 2 Nix closures and the locked Lake dependencies/Mathlib caches
must be available, as for the original experiment. The first run also checks
the retained temporal proof library. This is substantial computation; the
new full-transition refinement alone took 2m23s and 18.5 GiB peak RSS here.
Subsequent runs can reuse Lake's dependency-checked proof objects.

The flow is:

1. [export.py](export.py): capture the original PyTorch model and export
   TorchLean JSON to `build/lean-flow/pytorch.json`. Python emits no Lean model
   and does not read the hardware SMT.
2. [Graph.lean](Graph.lean): parse using TorchLean's Lean graph/type validation;
   execute supported int32 operations node by node. [GraphProof.lean](GraphProof.lean)
   proves that the actual graph computes the modular dot product.
3. [SMT.lean](SMT.lean): parse Yosys FunctionalIR SMT and interpret its typed
   operations, lets, memories, outputs and next state. The SMT file is
   `build/lean-flow/accelerator.smt2`.
4. [TransferProof.lean](TransferProof.lean): prove that **every output and
   next-state field**, for arbitrary inputs/state, agrees with the retained
   circuit model. [Equivalence.lean](Equivalence.lean) then composes the existing
   436-edge transaction proof with the graph proof. No solver result or
   additional axiom is accepted as equivalence.

[Prepare.lean](Prepare.lean) restores the immutable SMT and proof sources from
the retained bundle, checking SHA-256 identities. [GenerateBridge.lean](GenerateBridge.lean)
generates record packing/unpacking **in Lean**; it supplies no correctness
assumption. The generated bridge and retained proof sources are checked by
Lean through Lake. Unsupported graph/SMT constructs fail explicitly.

The observable is the first accepted scalar payload after 436 positive edges,
including four reset edges, with Task 2's fixed ready/done signals. Each input
is 16 complete int32 words; arithmetic wraps modulo 2³². All permitted initial
registers and the initial start bit remain arbitrary. This proves one baseline
transaction; backpressure, repeated transactions and larger models need further
contracts and proofs.

The SMT **transfer function** receives caller-supplied state. Its separate
global `main-initial` assertions are parsed and type-checked, but do not bind
that function argument. The Task 2 initial relation supplies the two arbitrary
input memories. PyTorch capture/operator correspondence and RTL-to-SMT export
remain external boundaries. Writing the parsers in Lean does not itself prove
their correspondence to PyTorch or the SMT-LIB language specification.

`run.sh` directly rechecks `Main.lean`, which reparses both artifacts and checks
their equality to the data used in the proofs. A changed parsed graph or transfer
function cannot silently inherit an old cached theorem. The native interpreter controls exercise overflow,
signed operations, memories, rejection cases, and all transition fields; these
controls supplement the universal theorem.
