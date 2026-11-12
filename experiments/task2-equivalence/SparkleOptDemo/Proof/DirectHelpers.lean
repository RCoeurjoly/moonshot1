import DirectModels
import SharedMath
open Lean Elab Tactic
open SparkleProof SparkleCommon
namespace SparkleDirect

theorem append_ite_right {m n : Nat} (c : Prop) [Decidable c]
    (x : BitVec m) (y z : BitVec n) :
    x ++ (if c then y else z) = (if c then x ++ y else x ++ z) := by
  split <;> rfl

theorem append_ite_left {m n : Nat} (c : Prop) [Decidable c]
    (x y : BitVec m) (z : BitVec n) :
    (if c then x else y) ++ z = (if c then x ++ z else y ++ z) := by
  split <;> rfl

theorem merge_reset {n : Nat} (r a : BitVec 1) (x y : BitVec n) :
    (if r == 1#1 then x else if a == 1#1 then x else y) =
      (if (r ||| a) == 1#1 then x else y) := by
  have h : ∀ i j : Fin 2,
      (if BitVec.ofFin (w := 1) i == 1#1 then x else
        if BitVec.ofFin (w := 1) j == 1#1 then x else y) =
        (if ((BitVec.ofFin (w := 1) i) ||| (BitVec.ofFin (w := 1) j)) == 1#1 then x else y) := by
    simp only [Fin.forall_fin_succ, Fin.forall_fin_zero]
    repeat' constructor
    all_goals rfl
  exact h r.toFin a.toFin

theorem one_mux (x y : BitVec 1) :
    (if x == 1#1 then 1#1 else y) = (x ||| y) := by
  have h : ∀ i j : Fin 2,
      (if BitVec.ofFin (w := 1) i == 1#1 then 1#1 else BitVec.ofFin (w := 1) j) =
      (BitVec.ofFin (w := 1) i ||| BitVec.ofFin (w := 1) j) := by decide
  exact h x.toFin y.toFin

theorem priority_mux_or {n : Nat} (a b : BitVec 1) (x y z : BitVec n) :
    (if (a ||| b) == 1#1 then (if a == 1#1 then x else y) else z) =
      (if a == 1#1 then x else if b == 1#1 then y else z) := by
  have h : ∀ i j : Fin 2,
      (if ((BitVec.ofFin (w := 1) i) ||| (BitVec.ofFin (w := 1) j)) == 1#1 then
        (if BitVec.ofFin (w := 1) i == 1#1 then x else y) else z) =
      (if BitVec.ofFin (w := 1) i == 1#1 then x else
        if BitVec.ofFin (w := 1) j == 1#1 then y else z) := by
    simp only [Fin.forall_fin_succ, Fin.forall_fin_zero]
    repeat' constructor
    all_goals rfl
  exact h a.toFin b.toFin

elab "unfold_direct_transition" : tactic => do
  let mut names : Array Ident := #[mkIdent `SparkleDirect.embed,
    mkIdent `SparkleDirect.inputs, mkIdent `SparkleDirect.outputs]
  let env ← getEnv
  for model in [`SparkleDirect.Baseline, `SparkleDirect.Optimized] do
    for name in ["evaluate", "outputs", "nextState"] do
      names := names.push (mkIdent (Name.str model name))
    for stem in ["wire", "next"] do
      let mut i := 0
      while env.contains (Name.str model s!"{stem}{i}") do
        names := names.push (mkIdent (Name.str model s!"{stem}{i}"))
        i := i + 1
  evalTactic (← `(tactic| dsimp +instances only [$[$names:ident],*]))

macro "close_direct_transition" : tactic => `(tactic| (
  unfold_direct_transition
  all_goals (try simp only [xor_one1, and_one1, one_and1, zero_eq_bit, native_bit_truth,
    neg_one1, mux_self1, bit_roundtrip1, concat_truth2, padded_bit4])
  all_goals (try simp only [word_write_bits32, word_write_mask_bits32_right])
  all_goals (try simp only [append_ite_right, append_ite_left])
  all_goals (try simp only [merge_reset, one_mux])
  all_goals (try simp only [BitVec.or_comm])
  all_goals (try simp only [priority_mux_or])
  all_goals bv_normalize (config := { acNf := true })
  all_goals (try simp_all only [xor_one1, and_one1, BitVec.not_not, mux_self1, mux_self1b])
  all_goals bv_normalize (config := { acNf := true })
  all_goals (try simp only [BitVec.and_comm, BitVec.or_comm] at *)
  all_goals bv_normalize (config := { acNf := true })
))
end SparkleDirect
