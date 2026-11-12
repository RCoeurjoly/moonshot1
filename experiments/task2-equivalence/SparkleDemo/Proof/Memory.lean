import Lean
set_option maxRecDepth 65536
set_option maxHeartbeats 0
namespace SparkleProof

private theorem memory_mux16_four (m : BitVec 4 → BitVec 32) (a : BitVec 4) :
    (if (BitVec.extractLsb' 3 1 a ≠ 0) then (if (BitVec.extractLsb' 2 1 a ≠ 0) then (if (BitVec.extractLsb' 1 1 a ≠ 0) then (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 15#4 else m 14#4) else (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 13#4 else m 12#4)) else (if (BitVec.extractLsb' 1 1 a ≠ 0) then (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 11#4 else m 10#4) else (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 9#4 else m 8#4))) else (if (BitVec.extractLsb' 2 1 a ≠ 0) then (if (BitVec.extractLsb' 1 1 a ≠ 0) then (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 7#4 else m 6#4) else (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 5#4 else m 4#4)) else (if (BitVec.extractLsb' 1 1 a ≠ 0) then (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 3#4 else m 2#4) else (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 1#4 else m 0#4)))) = m a := by
  have h : ∀ i : Fin 16,
      (if (BitVec.extractLsb' 3 1 (BitVec.ofFin (w := 4) i) ≠ 0) then (if (BitVec.extractLsb' 2 1 (BitVec.ofFin (w := 4) i) ≠ 0) then (if (BitVec.extractLsb' 1 1 (BitVec.ofFin (w := 4) i) ≠ 0) then (if (BitVec.extractLsb' 0 1 (BitVec.ofFin (w := 4) i) ≠ 0) then m 15#4 else m 14#4) else (if (BitVec.extractLsb' 0 1 (BitVec.ofFin (w := 4) i) ≠ 0) then m 13#4 else m 12#4)) else (if (BitVec.extractLsb' 1 1 (BitVec.ofFin (w := 4) i) ≠ 0) then (if (BitVec.extractLsb' 0 1 (BitVec.ofFin (w := 4) i) ≠ 0) then m 11#4 else m 10#4) else (if (BitVec.extractLsb' 0 1 (BitVec.ofFin (w := 4) i) ≠ 0) then m 9#4 else m 8#4))) else (if (BitVec.extractLsb' 2 1 (BitVec.ofFin (w := 4) i) ≠ 0) then (if (BitVec.extractLsb' 1 1 (BitVec.ofFin (w := 4) i) ≠ 0) then (if (BitVec.extractLsb' 0 1 (BitVec.ofFin (w := 4) i) ≠ 0) then m 7#4 else m 6#4) else (if (BitVec.extractLsb' 0 1 (BitVec.ofFin (w := 4) i) ≠ 0) then m 5#4 else m 4#4)) else (if (BitVec.extractLsb' 1 1 (BitVec.ofFin (w := 4) i) ≠ 0) then (if (BitVec.extractLsb' 0 1 (BitVec.ofFin (w := 4) i) ≠ 0) then m 3#4 else m 2#4) else (if (BitVec.extractLsb' 0 1 (BitVec.ofFin (w := 4) i) ≠ 0) then m 1#4 else m 0#4)))) = m (BitVec.ofFin (w := 4) i) := by
    simp only [Fin.forall_fin_succ, Fin.forall_fin_zero]
    repeat' constructor
    all_goals rfl
  exact h a.toFin

/-- Fold the actual Sparkle input-RAM mux tree into an arbitrary memory read.
    Only the low four address bits are used; all 64-bit addresses are covered. -/
theorem memory_mux16 (m : BitVec 4 → BitVec 32) (a : BitVec 64) :
    (if (BitVec.extractLsb' 3 1 a ≠ 0) then (if (BitVec.extractLsb' 2 1 a ≠ 0) then (if (BitVec.extractLsb' 1 1 a ≠ 0) then (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 15#4 else m 14#4) else (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 13#4 else m 12#4)) else (if (BitVec.extractLsb' 1 1 a ≠ 0) then (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 11#4 else m 10#4) else (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 9#4 else m 8#4))) else (if (BitVec.extractLsb' 2 1 a ≠ 0) then (if (BitVec.extractLsb' 1 1 a ≠ 0) then (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 7#4 else m 6#4) else (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 5#4 else m 4#4)) else (if (BitVec.extractLsb' 1 1 a ≠ 0) then (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 3#4 else m 2#4) else (if (BitVec.extractLsb' 0 1 a ≠ 0) then m 1#4 else m 0#4)))) = m (BitVec.extractLsb' 0 4 a) := by
  have h := memory_mux16_four m (BitVec.extractLsb' 0 4 a)
  simpa only [BitVec.extractLsb'_extractLsb'_of_le (by decide : (3 : Nat) + 1 ≤ 4),
    BitVec.extractLsb'_extractLsb'_of_le (by decide : (2 : Nat) + 1 ≤ 4),
    BitVec.extractLsb'_extractLsb'_of_le (by decide : (1 : Nat) + 1 ≤ 4),
    BitVec.extractLsb'_extractLsb'_of_le (by decide : (0 : Nat) + 1 ≤ 4)] using h

#print axioms memory_mux16
end SparkleProof
