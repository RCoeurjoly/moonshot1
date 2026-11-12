# Reading the universal proof

Start with [Main.lean](Main.lean). Its public statements are:

```lean
SparkleProof.Main.observable_equivalence
SparkleProof.Main.first_result
```

`observable_equivalence` says the imported hardware implements the source dot
product for every allowed pair of length-16 word vectors and every permitted
initial state. `first_result` fixes the first completion at 436 rising edges,
with the result `Task2.dot32 a b`.

## The argument

1. [Model.lean](Model.lean) loads the actual native Sparkle source. The
   [reference adapter](ReferenceAdapter.lean) changes record coordinates.
2. [prove.py](../prove.py) generates 453 next-state equalities and five output
   equalities against the retained reference transition. These quantify over
   arbitrary raw state and inputs, not merely reachable simulation states.
3. Generated `Assemble.lean` combines all 458 field proofs into complete
   `transfer_agrees`. Definitions and transition-defined flags agree too.
4. [Equivalence.lean](Equivalence.lean) lifts transfer equality through a step,
   a run and the transaction contract. Only then does it apply the unchanged
   Task 2 temporal theorem and its first-result theorem.
5. [Main.lean](Main.lean) independently reloads the current native artifact.
   `artifact_checked` ties the public statements to that fresh definition.

The retained model/library was produced in the original demo. It is a reference
dependency, not the importer for this demo. The new imported model's expressions
come from Sparkle's upstream `VerifyEmit.denote`.

## Supporting lemmas

| File | What it proves |
| --- | --- |
| [Helpers.lean](Helpers.lean) | Equivalent one-bit guards, mask shifts and local bit identities; a tactic that unfolds both transitions. |
| [Memory.lean](Memory.lean) | The 16-way native input mux equals an arbitrary memory read at the low four address bits. |
| [WordWrites.lean](WordWrites.lean) | The left-associated per-bit output update coalesces into a word update. |
| [WordWritesMaskRight.lean](WordWritesMaskRight.lean) | The corresponding right-associated mask update. |
| [OutputWord.lean](OutputWord.lean) | Their application to the writable output-memory word. |
| [NativeArtifact.lean](NativeArtifact.lean) | Restrict the generated-source format and load it into a fresh namespace. |

These are ordinary kernel-checked mathematical identities. The proof path
contains no custom circuit-operator interpretation. `bv_normalize` simplifies
terms; finite cases use kernel proofs. Axiom audits reject `sorryAx` and native
or solver evaluation axioms.

`run.sh proof` checks the existing artifact. `run.sh` first regenerates it from
RTL and repeats all controls. Both finish by mutating the native output by XOR 1
and requiring the fresh `artifact_checked` proof to fail.
