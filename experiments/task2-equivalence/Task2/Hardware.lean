import Task2.WordDot

namespace Task2

/-- The imported hardware adapter must include driver state and clock sampling.
    Initial carries source-defined known bits and the two symbolic input memories. -/
structure Device where
  State : Type
  initial : Words → Words → State → Prop
  step : State → State
  result : State → Option Word

def run (d : Device) (s : d.State) : Nat → d.State
  | 0 => s
  | n + 1 => d.step (run d s n)

def FirstResult (d : Device) (s : d.State) (n : Nat) (expected : Word) : Prop :=
  d.result (run d s n) = some expected ∧
  ∀ m, m < n → d.result (run d s m) = none

/-- Total single-transaction correctness with a uniform completion bound.
    Existence prevents an impossible initialization relation from proving the claim. -/
def Implements (d : Device) (f : Words → Words → Except String Word) : Prop :=
  (∀ a b, ∃ s, d.initial a b s) ∧
  ∃ C : Nat, ∀ a b s, d.initial a b s →
    ∃ n v, n ≤ C ∧ FirstResult d s n v ∧ f a b = .ok v

/-- A finite symbolic trajectory certifies every covered transition. -/
theorem run_eq_trace (d : Device) (trace : Nat → d.State) (C : Nat)
    (steps : ∀ n, n < C → d.step (trace n) = trace (n + 1)) :
    ∀ n, n ≤ C → run d (trace 0) n = trace n := by
  intro n hn
  induction n with
  | zero => rfl
  | succ n ih =>
    rw [run, ih (by omega), steps n (by omega)]

theorem firstResult_of_trace (d : Device) (trace : Nat → d.State) (C : Nat) (v : Word)
    (steps : ∀ n, n < C → d.step (trace n) = trace (n + 1))
    (completed : d.result (trace C) = some v)
    (earlier : ∀ n, n < C → d.result (trace n) = none) :
    FirstResult d (trace 0) C v := by
  constructor
  · rw [run_eq_trace d trace C steps C (by omega)]
    exact completed
  · intro n hn
    rw [run_eq_trace d trace C steps n (by omega)]
    exact earlier n hn

end Task2
