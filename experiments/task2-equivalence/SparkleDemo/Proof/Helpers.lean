import Model
import Memory
import WordWrites
import WordWritesMaskRight
import Std.Tactic.BVDecide

open Lean Elab Tactic
namespace SparkleProof

theorem xor_one1 (x : BitVec 1) : x ^^^ (1#1) = ~~~x := BitVec.xor_allOnes
theorem and_one1 (x : BitVec 1) : x &&& (1#1) = x := BitVec.and_allOnes
theorem one_and1 (x : BitVec 1) : (1#1) &&& x = x := BitVec.allOnes_and
theorem zero_eq_bit : (if 0#1 == 0#1 then 1#1 else 0#1) = 1#1 := rfl
theorem bit_truth (x : BitVec 1) : (x != 0) = (x == 1#1) := by
  have h : ∀ i : Fin 2, ((BitVec.ofFin (w := 1) i) != 0) =
      ((BitVec.ofFin (w := 1) i) == 1#1) := by decide
  exact h x.toFin

-- Sparkle emits proposition-valued guards; the reference uses a one-bit test.
theorem native_bit_truth (x : BitVec 1) : (x ≠ 0) ↔ (x == 1#1) = true := by
  have h : ∀ i : Fin 2, (BitVec.ofFin (w := 1) i ≠ 0) ↔
      (BitVec.ofFin (w := 1) i == 1#1) = true := by decide
  exact h x.toFin

-- The RTL shifts a two-bit mask by a single bit. Both importers use the
-- standard BitVec shift; this lemma relates their shift-amount encodings.
theorem native_shift2 (x : BitVec 2) (amount : BitVec 1) :
    (x <<< amount) = (x <<< Nat.min 2 amount.toNat) := by
  have h : ∀ i : Fin 2, (x <<< BitVec.ofFin (w := 1) i) =
      (x <<< Nat.min 2 (BitVec.ofFin (w := 1) i).toNat) := by
    simp only [Fin.forall_fin_succ, Fin.forall_fin_zero]
    repeat' constructor
    all_goals rfl
  exact h amount.toFin

theorem neg_one1 : -(1 : BitVec 1) = 1#1 := rfl

theorem mux_self1 (x y : BitVec 1) :
    (if x == 1#1 then x else y) = (if x == 1#1 then 1#1 else y) := by
  split <;> simp_all

theorem mux_self1b (x y : BitVec 1) :
    (bif x == 1#1 then x else y) = (bif x == 1#1 then 1#1 else y) := by
  cases h : x == 1#1 <;> simp_all

theorem extend1 (x : BitVec 1) : BitVec.setWidth 2 x = (0#1 ++ x) := by
  have h : ∀ i : Fin 2, BitVec.setWidth 2 (BitVec.ofFin (w := 1) i) =
      (0#1 ++ BitVec.ofFin (w := 1) i) := by decide
  exact h x.toFin

theorem append_zero1_toNat (x : BitVec 1) : (0#1 ++ x).toNat = x.toNat := by
  have h : ∀ i : Fin 2, (0#1 ++ BitVec.ofFin (w := 1) i).toNat =
      (BitVec.ofFin (w := 1) i).toNat := by decide
  exact h x.toFin

theorem bit_roundtrip1 (x : BitVec 1) : (if x == 1#1 then 1#1 else 0#1) = x := by
  have h : ∀ i : Fin 2, (if BitVec.ofFin (w := 1) i == 1#1 then 1#1 else 0#1) =
      BitVec.ofFin (w := 1) i := by decide
  exact h x.toFin

elab "unfold_transition" : tactic => do
  let mut names : Array Ident := #[mkIdent `SparkleProof.evaluate,
    mkIdent `Task2.Imported.BaselineCore.evaluate]
  let env ← getEnv
  for name in ["evaluate_inputs", "evaluate_state", "evaluate_next", "evaluate_outputs"] do
    names := names.push (mkIdent (Name.str `SparkleProof name))
  for name in ["evaluate", "outputs", "nextState"] do
    names := names.push (mkIdent (Name.str `SparkleProof.RTL name))
  for stem in ["wire", "next"] do
    let mut i := 0
    while env.contains (Name.str `SparkleProof.RTL s!"{stem}{i}") do
      names := names.push (mkIdent (Name.str `SparkleProof.RTL s!"{stem}{i}"))
      i := i + 1
  for chunk in [:50] do
    names := names.push (mkIdent (Name.str `Task2.Imported.BaselineCore s!"c2lChunk{chunk}"))
  evalTactic (← `(tactic| dsimp +instances only [$[$names:ident],*]))

macro "close_transition" : tactic => `(tactic| (
  unfold_transition
  all_goals (try simp only [memory_mux16])
  all_goals (try simp only [xor_one1, and_one1, one_and1, zero_eq_bit, bit_truth, native_bit_truth, neg_one1, native_shift2,
    mux_self1, extend1, append_zero1_toNat, BitVec.slt_eq_decide, bit_roundtrip1])
  all_goals (try simp only [word_write_bits32, word_write_mask_bits32_right])
  all_goals bv_normalize
  all_goals (try simp_all only [xor_one1, and_one1, BitVec.not_not, mux_self1, mux_self1b,
    extend1, append_zero1_toNat])
  all_goals bv_normalize
))
end SparkleProof
