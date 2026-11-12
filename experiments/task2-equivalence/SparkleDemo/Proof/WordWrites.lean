import Lean
import Std.Tactic.BVDecide
set_option maxRecDepth 65536
set_option maxHeartbeats 0
namespace SparkleProof

/-- Coalesce the imported per-bit priority writes into one word update. -/
theorem word_write_bits32 (c0 c1 : BitVec 1) (d0 d1 old : BitVec 32) :
    ((((((((((((((((((((((((((((((((if BitVec.extractLsb' 31 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 31 1 d1 else if BitVec.extractLsb' 31 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 31 1 d0 else BitVec.extractLsb' 31 1 old) ++
      (if BitVec.extractLsb' 30 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 30 1 d1 else if BitVec.extractLsb' 30 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 30 1 d0 else BitVec.extractLsb' 30 1 old)) ++
      (if BitVec.extractLsb' 29 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 29 1 d1 else if BitVec.extractLsb' 29 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 29 1 d0 else BitVec.extractLsb' 29 1 old)) ++
      (if BitVec.extractLsb' 28 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 28 1 d1 else if BitVec.extractLsb' 28 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 28 1 d0 else BitVec.extractLsb' 28 1 old)) ++
      (if BitVec.extractLsb' 27 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 27 1 d1 else if BitVec.extractLsb' 27 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 27 1 d0 else BitVec.extractLsb' 27 1 old)) ++
      (if BitVec.extractLsb' 26 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 26 1 d1 else if BitVec.extractLsb' 26 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 26 1 d0 else BitVec.extractLsb' 26 1 old)) ++
      (if BitVec.extractLsb' 25 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 25 1 d1 else if BitVec.extractLsb' 25 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 25 1 d0 else BitVec.extractLsb' 25 1 old)) ++
      (if BitVec.extractLsb' 24 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 24 1 d1 else if BitVec.extractLsb' 24 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 24 1 d0 else BitVec.extractLsb' 24 1 old)) ++
      (if BitVec.extractLsb' 23 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 23 1 d1 else if BitVec.extractLsb' 23 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 23 1 d0 else BitVec.extractLsb' 23 1 old)) ++
      (if BitVec.extractLsb' 22 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 22 1 d1 else if BitVec.extractLsb' 22 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 22 1 d0 else BitVec.extractLsb' 22 1 old)) ++
      (if BitVec.extractLsb' 21 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 21 1 d1 else if BitVec.extractLsb' 21 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 21 1 d0 else BitVec.extractLsb' 21 1 old)) ++
      (if BitVec.extractLsb' 20 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 20 1 d1 else if BitVec.extractLsb' 20 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 20 1 d0 else BitVec.extractLsb' 20 1 old)) ++
      (if BitVec.extractLsb' 19 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 19 1 d1 else if BitVec.extractLsb' 19 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 19 1 d0 else BitVec.extractLsb' 19 1 old)) ++
      (if BitVec.extractLsb' 18 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 18 1 d1 else if BitVec.extractLsb' 18 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 18 1 d0 else BitVec.extractLsb' 18 1 old)) ++
      (if BitVec.extractLsb' 17 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 17 1 d1 else if BitVec.extractLsb' 17 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 17 1 d0 else BitVec.extractLsb' 17 1 old)) ++
      (if BitVec.extractLsb' 16 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 16 1 d1 else if BitVec.extractLsb' 16 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 16 1 d0 else BitVec.extractLsb' 16 1 old)) ++
      (if BitVec.extractLsb' 15 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 15 1 d1 else if BitVec.extractLsb' 15 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 15 1 d0 else BitVec.extractLsb' 15 1 old)) ++
      (if BitVec.extractLsb' 14 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 14 1 d1 else if BitVec.extractLsb' 14 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 14 1 d0 else BitVec.extractLsb' 14 1 old)) ++
      (if BitVec.extractLsb' 13 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 13 1 d1 else if BitVec.extractLsb' 13 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 13 1 d0 else BitVec.extractLsb' 13 1 old)) ++
      (if BitVec.extractLsb' 12 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 12 1 d1 else if BitVec.extractLsb' 12 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 12 1 d0 else BitVec.extractLsb' 12 1 old)) ++
      (if BitVec.extractLsb' 11 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 11 1 d1 else if BitVec.extractLsb' 11 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 11 1 d0 else BitVec.extractLsb' 11 1 old)) ++
      (if BitVec.extractLsb' 10 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 10 1 d1 else if BitVec.extractLsb' 10 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 10 1 d0 else BitVec.extractLsb' 10 1 old)) ++
      (if BitVec.extractLsb' 9 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 9 1 d1 else if BitVec.extractLsb' 9 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 9 1 d0 else BitVec.extractLsb' 9 1 old)) ++
      (if BitVec.extractLsb' 8 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 8 1 d1 else if BitVec.extractLsb' 8 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 8 1 d0 else BitVec.extractLsb' 8 1 old)) ++
      (if BitVec.extractLsb' 7 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 7 1 d1 else if BitVec.extractLsb' 7 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 7 1 d0 else BitVec.extractLsb' 7 1 old)) ++
      (if BitVec.extractLsb' 6 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 6 1 d1 else if BitVec.extractLsb' 6 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 6 1 d0 else BitVec.extractLsb' 6 1 old)) ++
      (if BitVec.extractLsb' 5 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 5 1 d1 else if BitVec.extractLsb' 5 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 5 1 d0 else BitVec.extractLsb' 5 1 old)) ++
      (if BitVec.extractLsb' 4 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 4 1 d1 else if BitVec.extractLsb' 4 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 4 1 d0 else BitVec.extractLsb' 4 1 old)) ++
      (if BitVec.extractLsb' 3 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 3 1 d1 else if BitVec.extractLsb' 3 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 3 1 d0 else BitVec.extractLsb' 3 1 old)) ++
      (if BitVec.extractLsb' 2 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 2 1 d1 else if BitVec.extractLsb' 2 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 2 1 d0 else BitVec.extractLsb' 2 1 old)) ++
      (if BitVec.extractLsb' 1 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 1 1 d1 else if BitVec.extractLsb' 1 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 1 1 d0 else BitVec.extractLsb' 1 1 old)) ++
      (if BitVec.extractLsb' 0 1 (if c1 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 0 1 d1 else if BitVec.extractLsb' 0 1 (if c0 == 1#1 then 4294967295#32 else 0#32) == 1#1 then BitVec.extractLsb' 0 1 d0 else BitVec.extractLsb' 0 1 old)) =
      (if c1 == 1#1 then d1 else if c0 == 1#1 then d0 else old) := by
  cases h0 : (c0 == 1#1) <;> cases h1 : (c1 == 1#1) <;>
    simp only [h0, h1, Bool.false_eq_true, ite_false, ite_true] <;>
    bv_normalize

#print axioms word_write_bits32
end SparkleProof
