import OptModel
import SharedMath

open Lean Elab Tactic
open SparkleProof SparkleCommon
namespace SparkleOptProof

elab "unfold_opt_transition" : tactic => do
  let mut names : Array Ident := #[mkIdent `SparkleOptProof.evaluate,
    mkIdent `Task2.Imported.CandidateCore.evaluate]
  let env ← getEnv
  for name in ["evaluate_inputs", "evaluate_state", "evaluate_next", "evaluate_outputs"] do
    names := names.push (mkIdent (Name.str `SparkleOptProof name))
  for name in ["evaluate", "outputs", "nextState"] do
    names := names.push (mkIdent (Name.str `SparkleOptProof.RTL name))
  for stem in ["wire", "next"] do
    let mut i := 0
    while env.contains (Name.str `SparkleOptProof.RTL s!"{stem}{i}") do
      names := names.push (mkIdent (Name.str `SparkleOptProof.RTL s!"{stem}{i}"))
      i := i + 1
  let mut chunk := 0
  while env.contains (Name.str `Task2.Imported.CandidateCore s!"c2lChunk{chunk}") do
    names := names.push (mkIdent (Name.str `Task2.Imported.CandidateCore s!"c2lChunk{chunk}"))
    chunk := chunk + 1
  evalTactic (← `(tactic| dsimp +instances only [$[$names:ident],*]))

macro "close_opt_transition" : tactic => `(tactic| (
  unfold_opt_transition
  all_goals (try simp only [memory_mux16])
  all_goals (try simp only [xor_one1, and_one1, one_and1, zero_eq_bit, concat_truth2, padded_bit4, bit_truth, native_bit_truth, neg_one1, native_shift2,
    mux_self1, extend1, append_zero1_toNat, BitVec.slt_eq_decide, bit_roundtrip1])
  all_goals (try simp only [word_write_bits32, word_write_mask_bits32_right])
  all_goals bv_normalize (config := { acNf := true })
  all_goals (try simp_all only [xor_one1, and_one1, BitVec.not_not, mux_self1, mux_self1b,
    extend1, append_zero1_toNat, padded_bit4])
  all_goals bv_normalize (config := { acNf := true })
  all_goals (try simp only [BitVec.and_comm, BitVec.or_comm] at *)
  all_goals bv_normalize (config := { acNf := true })
))
end SparkleOptProof
