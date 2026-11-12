import Helpers
import Task2.ProofTools
set_option maxRecDepth 65536
set_option maxHeartbeats 0
namespace SparkleProof
/-- Coalesce both independently imported output-word updates. The explicit
    arguments let the kernel check their correspondence without relying on
    heuristic rewriting of the full concatenation. -/
theorem agrees_s380 (inputs : Task2.Imported.BaselineCore.Inputs) (state : Task2.Imported.BaselineCore.State) :
    (evaluate inputs state).nextState.g2.s380 =
    (Task2.Imported.BaselineCore.evaluate inputs state).nextState.g2.s380 := by
  unfold_transition
  simp only [xor_one1, and_one1, one_and1, zero_eq_bit, bit_truth, native_bit_truth, neg_one1,
    mux_self1, extend1, append_zero1_toNat, bit_roundtrip1]
  simp only [word_write_bits32]
  have h := word_write_mask_bits32_right
    (if inputs.i0 == 1#1 then 0#1 else
      (if state.g2.s340 == 1#1 then 1#1 else state.g2.s341) &&&
      (if state.g2.s371 == 1#1 then 1#1 else state.g2.s350))
    (if inputs.i0 == 1#1 then 0#1 else
      (if state.g2.s348 == 1#1 then 1#1 else state.g2.s349) &&&
      (if state.g2.s374 == 1#1 then 1#1 else state.g2.s355))
    (if state.g2.s371 == 1#1 then state.g2.s372 else state.g2.s373)
    (if state.g2.s374 == 1#1 then state.g2.s375 else state.g2.s376)
    state.g2.s380
  kernel_exact h.symm
#print axioms agrees_s380
end SparkleProof
