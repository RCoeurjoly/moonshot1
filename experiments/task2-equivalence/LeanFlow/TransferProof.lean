import LeanFlow.Bridge
import Task2.ProofTools

set_option maxRecDepth 65536
set_option maxHeartbeats 0

namespace LeanFlow

/-- Every output and next-state field, for arbitrary inputs and raw state.
    This connects the explicit SMT interpreter to the retained circuit proof. -/
theorem transfer_agrees (inputs : Bridge.CoreInputs) (state : Bridge.CoreState) :
    Bridge.transfer inputs state =
      .ok ((Task2.Imported.BaselineCore.evaluate inputs state).outputs,
           (Task2.Imported.BaselineCore.evaluate inputs state).nextState) := by
  kernel_rfl

#print axioms transfer_agrees
end LeanFlow
