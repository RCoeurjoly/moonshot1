import LeanFlow.GraphProof
import LeanFlow.TransferProof
import Task2.Baseline

namespace LeanFlow
namespace Hardware

abbrev State := Task2.Imported.BaselineAdapter.State

/-- The same positive-edge driver as Task 2, with the parsed SMT interpreter
    supplying the transition. Errors stall; the canonical transfer theorem
    proves this error branch unreachable for every input and state. -/
def finish (s : State) (result : Except String (Bridge.CoreOutputs × Bridge.CoreState)) : State :=
  match result with
  | .error _ => s
  | .ok (outputs,nextState) =>
    { raw := nextState, cycles := s.cycles+1,
      start := if s.cycles < 4 then true else if outputs.o1 != 0 then false else s.start,
      observed := if s.cycles < 4 then none else if outputs.o4 == 1 then some outputs.o3 else none }

def step (hardware : SMT.Program) (s : State) : State :=
  finish s (Bridge.transferFor hardware (Task2.Imported.BaselineAdapter.inputs s) s.raw)

def device (hardware : SMT.Program) : Task2.Device where
  State := State
  initial := Task2.Imported.BaselineAdapter.initial
  step := step hardware
  result := (·.observed)

theorem step_agrees (s : State) :
    step accelerator s = Task2.Imported.BaselineAdapter.step s := by
  kernel_exact congrArg (finish s)
    (transfer_agrees (Task2.Imported.BaselineAdapter.inputs s) s.raw)

theorem device_agrees : device accelerator = Task2.Imported.baseline := by
  have h : step accelerator = Task2.Imported.BaselineAdapter.step := funext step_agrees
  unfold device Task2.Imported.baseline
  rw [h]

end Hardware

/-- All complete int32 input words and all permitted raw initial states,
    under Task 2's four-reset-edge and fixed-ready transaction contract. -/
theorem equivalence :
    Task2.Implements (Hardware.device accelerator) (Graph.scalar pytorch) := by
  rw [Hardware.device_agrees]
  have source : Graph.scalar pytorch = Task2.sourceEval := by
    funext a b
    exact (pytorch_agrees a b).trans (Task2.source_agrees a b).symm
  rw [source]
  exact Task2.baseline_correct

#print axioms equivalence
end LeanFlow
