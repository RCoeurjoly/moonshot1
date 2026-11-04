import LeanFlow.SMT

set_option maxRecDepth 65536
set_option maxHeartbeats 0

namespace LeanFlow
import_hardware_smt "build/lean-flow/accelerator.smt2" as accelerator
end LeanFlow
