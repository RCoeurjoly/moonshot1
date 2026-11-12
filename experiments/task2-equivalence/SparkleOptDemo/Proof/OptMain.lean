import OptEquivalence

set_option maxRecDepth 65536
set_option maxHeartbeats 0
namespace SparkleOptProof.Main

-- Re-read the actual artifact on every direct invocation. A changed circuit
-- cannot inherit the previously checked field and transaction proofs.
import_native_sparkle "build/native/Task2RTL.lean" as RTL
adapt_opt_reference "build/bindings.json" as checked

theorem artifact_checked : checked = SparkleOptProof.evaluate := by
  funext inputs state
  kernel_rfl

theorem observable_equivalence :
    Task2.Implements (Hardware.device checked) Task2.sourceEval := by
  rw [artifact_checked]
  exact SparkleOptProof.universal_equivalence

theorem first_result (a b : Task2.Words) (s : Hardware.State)
    (h : (Hardware.device checked).initial a b s) :
    Task2.FirstResult (Hardware.device checked) s 436 (Task2.dot32 a b) := by
  rw [artifact_checked] at h ⊢
  exact SparkleOptProof.first_result a b s h

#print observable_equivalence
#print axioms observable_equivalence
#print axioms first_result
end SparkleOptProof.Main
