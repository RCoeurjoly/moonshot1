import Task2.WordDot
import Task2.Imported.Source

namespace Task2

/-- Keep static acceptance separate so its finite computation can be checked
    by the kernel even when upstream definitions carry irreducibility hints. -/
def acceptsIntegerDot (program : NN.IR.Program) : Bool :=
  match program.check with
  | .error _ => false
  | .ok _ =>
    program.inputs == #[0, 1] && program.outputs == #[2] &&
      program.dtypes == #[.integer true (some 32), .integer true (some 32),
        .integer true (some 32)] && program.primitives.all (·.isNone) &&
    match program.graph.nodes.toList with
    | [x, y, z] =>
      x.kind == .input && y.kind == .input && z.kind == .matmul &&
        x.parents.isEmpty && y.parents.isEmpty && z.parents == #[0, 1] &&
        x.outShape == [16] && y.outShape == [16] && z.outShape == []
    | _ => false

/-- Narrow semantics for a checked rank-one signed-int32 contraction.
    Every other operation/interface is rejected. This extends TorchLean locally. -/
def evalIntegerDot (program : NN.IR.Program) (a b : Words) : Except String Word :=
  if acceptsIntegerDot program then
    .ok ((List.finRange 16).foldl (fun acc i => acc + a i * b i) 0)
  else .error "unsupported integer-dot graph"

theorem imported_supported : acceptsIntegerDot Imported.sourceProgram = true := by
  decide +kernel

def sourceEval (a b : Words) : Except String Word :=
  evalIntegerDot Imported.sourceProgram a b

theorem source_agrees (a b : Words) : sourceEval a b = .ok (dot32 a b) := by
  simp [sourceEval, evalIntegerDot, imported_supported, dot32]

end Task2
