import Memory
import WordWrites
import WordWritesMaskRight
import Std.Tactic.BVDecide

open Lean Elab Tactic
namespace SparkleCommon

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


-- Yosys expands a two-bit reduction into a one-bit OR gate.
-- This finite identity relates the two already-defined BitVec encodings.
theorem concat_truth2 (x y : BitVec 1) :
    (@bne (BitVec 2) inferInstance (x ++ y) (0#2)) = ((x ||| y) == 1#1) := by
  have h : ∀ i j : Fin 2,
      (@bne (BitVec 2) inferInstance (BitVec.ofFin (w := 1) i ++ BitVec.ofFin (w := 1) j) (0#2)) =
      ((BitVec.ofFin (w := 1) i ||| BitVec.ofFin (w := 1) j) == 1#1) := by decide
  exact h x.toFin y.toFin

theorem padded_bit4 (x : BitVec 1) :
    @Eq (BitVec 64) ((0#59 ++ x) ++ 0#4) (0#59 ++ (x ++ 0#4)) := by
  have h : ∀ i : Fin 2,
      @Eq (BitVec 64) ((0#59 ++ BitVec.ofFin (w := 1) i) ++ 0#4)
        (0#59 ++ (BitVec.ofFin (w := 1) i ++ 0#4)) := by decide
  exact h x.toFin


end SparkleCommon
