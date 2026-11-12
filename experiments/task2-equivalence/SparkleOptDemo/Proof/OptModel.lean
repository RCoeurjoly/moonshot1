import OptReferenceAdapter
set_option maxRecDepth 65536
set_option maxHeartbeats 0
namespace SparkleOptProof
import_native_sparkle "build/native/Task2RTL.lean" as RTL
adapt_opt_reference "build/bindings.json" as evaluate
end SparkleOptProof
