import OptAssemble
import Task2.Candidate

namespace SparkleOptProof
namespace Hardware

abbrev State := Task2.Imported.CandidateAdapter.State
abbrev Transfer := Task2.Imported.CandidateCore.Inputs →
  Task2.Imported.CandidateCore.State → Task2.Imported.CandidateCore.Evaluation

def step (transfer : Transfer) (s : State) : State :=
  let r := transfer (Task2.Imported.CandidateAdapter.inputs s) s.raw
  { raw := r.nextState, cycles := s.cycles + 1,
    start := if s.cycles < 4 then true else if r.outputs.o1 != 0 then false else s.start,
    observed := if s.cycles < 4 then none else if r.outputs.o4 == 1 then some r.outputs.o3 else none }

def device (transfer : Transfer) : Task2.Device where
  State := State
  initial := Task2.Imported.CandidateAdapter.initial
  step := step transfer
  result := (·.observed)

theorem step_agrees (s : State) :
    step evaluate s = Task2.Imported.CandidateAdapter.step s := by
  unfold step
  rw [transfer_agrees]
  rfl

theorem device_agrees : device evaluate = Task2.Imported.candidate := by
  have h : step evaluate = Task2.Imported.CandidateAdapter.step := funext step_agrees
  unfold device Task2.Imported.candidate
  rw [h]

theorem run_agrees (s : State) (n : Nat) :
    Task2.run (device evaluate) s n = Task2.run Task2.Imported.candidate s n := by
  induction n with
  | zero => rfl
  | succ n ih =>
    kernel_exact Eq.trans (step_agrees (Task2.run (device evaluate) s n))
      (congrArg Task2.Imported.CandidateAdapter.step ih)

end Hardware

/-- All pairs of 16 complete int32 words and every permitted raw initial state.
    The retained temporal theorem applies only after the new full transition
    equivalence above. -/
theorem universal_equivalence :
    Task2.Implements (Hardware.device evaluate) Task2.sourceEval := by
  rw [Hardware.device_agrees]
  exact Task2.candidate_correct

theorem first_result (a b : Task2.Words) (s : Hardware.State)
    (h : (Hardware.device evaluate).initial a b s) :
    Task2.FirstResult (Hardware.device evaluate) s 436 (Task2.dot32 a b) := by
  have original : Task2.FirstResult Task2.Imported.candidate s 436 (Task2.dot32 a b) := by
    have hp := Task2.Imported.CandidateTrace.initial_parameterization a b s h
    rw [hp]
    exact Task2.Imported.CandidateTrace.first_result a b s.raw s.start
  unfold Task2.FirstResult at original ⊢
  constructor
  · change (Task2.run (Hardware.device evaluate) s 436).observed = some (Task2.dot32 a b)
    kernel_exact Eq.trans
      (congrArg (fun t : Hardware.State => t.observed) (Hardware.run_agrees s 436)) original.1
  · intro n hn
    change (Task2.run (Hardware.device evaluate) s n).observed = none
    kernel_exact Eq.trans
      (congrArg (fun t : Hardware.State => t.observed) (Hardware.run_agrees s n)) (original.2 n hn)

#print axioms universal_equivalence
#print axioms first_result
end SparkleOptProof
