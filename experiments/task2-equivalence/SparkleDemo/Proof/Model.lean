import ReferenceAdapter
set_option maxRecDepth 65536
set_option maxHeartbeats 0
namespace SparkleProof
import_native_sparkle "build/native/Task2RTL.lean" as RTL
adapt_native_reference "build/bindings.json" as evaluate
end SparkleProof
