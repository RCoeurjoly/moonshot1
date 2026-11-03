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

end Task2
