import DirectAssemble
namespace SparkleDirect

abbrev BaselineTransfer := Baseline.Inputs → Baseline.State → Baseline.Evaluation
abbrev OptimizedTransfer := Optimized.Inputs → Optimized.State → Optimized.Evaluation

def runBaseline (transfer : BaselineTransfer) (stream : Nat → Optimized.Inputs)
    (initial : Baseline.State) : Nat → Baseline.State
  | 0 => initial
  | n + 1 => (transfer (inputs (stream n)) (runBaseline transfer stream initial n)).nextState

def runOptimized (transfer : OptimizedTransfer) (stream : Nat → Optimized.Inputs)
    (initial : Optimized.State) : Nat → Optimized.State
  | 0 => initial
  | n + 1 => (transfer (stream n) (runOptimized transfer stream initial n)).nextState

theorem run_agrees (stream : Nat → Optimized.Inputs) (state : Optimized.State) (n : Nat) :
    runBaseline Baseline.evaluate stream (embed state) n =
      embed (runOptimized Optimized.evaluate stream state n) := by
  induction n with
  | zero => rfl
  | succ n ih =>
    simp only [runBaseline, runOptimized]
    rw [ih]
    exact nextState_agrees (stream n) (runOptimized Optimized.evaluate stream state n)

theorem trace_outputs_agree (stream : Nat → Optimized.Inputs) (state : Optimized.State) (n : Nat) :
    outputs (Baseline.evaluate (inputs (stream n))
      (runBaseline Baseline.evaluate stream (embed state) n)).outputs =
      (Optimized.evaluate (stream n) (runOptimized Optimized.evaluate stream state n)).outputs := by
  rw [run_agrees]
  exact outputs_agree (stream n) (runOptimized Optimized.evaluate stream state n)

#print axioms run_agrees
#print axioms trace_outputs_agree
end SparkleDirect
