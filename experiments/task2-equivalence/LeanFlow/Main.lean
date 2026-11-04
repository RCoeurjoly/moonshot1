import LeanFlow.Equivalence

set_option maxRecDepth 65536
set_option maxHeartbeats 0

namespace LeanFlow.Main

-- These commands read and parse the actual files in Lean on each direct check.
import_pytorch_graph "build/lean-flow/pytorch.json" as model
import_hardware_smt "build/lean-flow/accelerator.smt2" as hardware

theorem observable_equivalence :
    Task2.Implements (Hardware.device hardware) (Graph.scalar model) := by
  have graph_checked : model = pytorch := by kernel_rfl
  have hardware_checked : hardware = accelerator := by kernel_rfl
  rw [graph_checked, hardware_checked]
  exact LeanFlow.equivalence

#print observable_equivalence
#print axioms observable_equivalence
end LeanFlow.Main
