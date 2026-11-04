import LeanFlow.GraphArtifact
import Task2.ProofTools

set_option maxRecDepth 65536
set_option maxHeartbeats 0

namespace LeanFlow

-- The target is execution of the imported nodes, for every input word.
theorem pytorch_agrees (a b : Task2.Words) :
    Graph.scalar pytorch a b = .ok (Task2.dot32 a b) := by
  kernel_rfl

#print axioms pytorch_agrees

end LeanFlow
