import NN.Runtime.IR
import Mathlib.Tactic.ToExpr
import Task2.WordDot

namespace LeanFlow.Graph

abbrev Word := BitVec 32

structure Tensor where
  shape : List Nat
  data : Array Word
  deriving BEq, Repr

inductive Op where
  | input | add | sub | mul | matmul | sum
  deriving BEq, Repr, Lean.ToExpr

structure Node where
  op : Op
  parents : Array Nat
  shape : List Nat
  deriving Repr, Lean.ToExpr

structure Program where
  nodes : Array Node
  inputs : Array Nat
  outputs : Array Nat
  deriving Repr, Lean.ToExpr

/-- TorchLean performs the graph/type/shape checks; this execution fragment
    additionally rejects every dtype and operator it does not implement. -/
def ofProgram (program : NN.IR.Program) : Except String Program := do
  program.check
  unless program.dtypes.all (· == .integer true (some 32)) do
    throw "LeanFlow: only signed int32 graph execution is implemented"
  unless program.primitives.all (·.isNone) do
    throw "LeanFlow: custom primitives are not implemented"
  let nodes ← program.graph.nodes.mapM fun node => do
    let op ← match node.kind with
      | .input => pure Op.input
      | .add => pure .add
      | .sub => pure .sub
      | .mulElem => pure .mul
      | .matmul => pure .matmul
      | .sum => pure .sum
      | other => throw s!"LeanFlow: unsupported graph operator {other.tag}"
    pure ⟨op, node.parents, node.outShape⟩
  pure ⟨nodes, program.inputs, program.outputs⟩

def parse (text : String) : Except String Program := do
  let json ← Lean.Json.parse text
  unless (← json.getObjValAs? String "format") == "torchlean.ir.v2" &&
      (← json.getObjValAs? String "frontend") == "pytorch" do
    throw "LeanFlow: expected a PyTorch torchlean.ir.v2 graph"
  unless (← (← json.getObjVal? "capture_constraints").getArr?).isEmpty do
    throw "LeanFlow: capture constraints require explicit semantics"
  ofProgram (← Import.IR.parseProgram json)

def Tensor.check (tensor : Tensor) : Except String Unit := do
  unless tensor.data.size == tensor.shape.prod do
    throw "LeanFlow: tensor word count disagrees with its shape"

def Tensor.word (tensor : Tensor) (index : Nat) : Except String Word :=
  match tensor.data[index]? with
  | some value => .ok value
  | none => .error "LeanFlow: tensor index out of bounds"

def matmul (left right : Tensor) : Except String Tensor := do
  left.check; right.check
  let dims ← NN.IR.OpContracts.matmulDims left.shape right.shape
  let data ← (List.finRange (Spec.Shape.size dims.outShape)).toArray.mapM fun output =>
    (List.finRange dims.inner).foldlM (fun acc inner => do
      let a ← left.word (dims.leftIndex output.val inner.val)
      let b ← right.word (dims.rightIndex output.val inner.val)
      pure (acc + a * b)) (0 : Word)
  pure ⟨dims.outShape, data⟩

def binary (op : Word → Word → Word) (left right : Tensor) : Except String Tensor := do
  left.check; right.check
  unless left.shape == right.shape do throw "LeanFlow: binary operands require equal shapes"
  pure ⟨left.shape, left.data.zipWith op right.data⟩

def evalNode (program : Program) (arguments values : Array Tensor) (index : Nat)
    (node : Node) : Except String Tensor := do
  let parent (position : Nat) : Except String Tensor := do
    let some id := node.parents[position]? | throw "LeanFlow: missing parent"
    unless id < index do throw "LeanFlow: forward or cyclic graph reference"
    let some tensor := values[id]? | throw "LeanFlow: missing parent value"
    pure tensor
  let result ← match node.op with
    | .input => do
      let some position := program.inputs.findIdx? (· == index) | throw "LeanFlow: unregistered input"
      let some value := arguments[position]? | throw "LeanFlow: missing argument"
      pure value
    | .add => binary (· + ·) (← parent 0) (← parent 1)
    | .sub => binary (· - ·) (← parent 0) (← parent 1)
    | .mul => binary (· * ·) (← parent 0) (← parent 1)
    | .matmul => matmul (← parent 0) (← parent 1)
    | .sum => do
      let value ← parent 0
      pure ⟨[], #[value.data.toList.foldl (· + ·) 0]⟩
  result.check
  unless result.shape == node.shape do throw "LeanFlow: result shape disagrees with graph"
  pure result

/-- Executes the imported nodes in order; there is no whole-model recognizer. -/
def eval (program : Program) (arguments : Array Tensor) : Except String (Array Tensor) := do
  unless arguments.size == program.inputs.size do throw "LeanFlow: wrong argument count"
  let mut values := #[]
  for node in program.nodes do
    values := values.push (← evalNode program arguments values values.size node)
  program.outputs.mapM fun id => do
    let some value := values[id]? | throw "LeanFlow: missing output"
    pure value

def scalar (program : Program) (a b : Task2.Words) : Except String Word := do
  let values ← eval program #[⟨[16], Array.ofFn a⟩, ⟨[16], Array.ofFn b⟩]
  match values.toList with
  | [⟨[], data⟩] =>
    match data.toList with
    | [value] => pure value
    | _ => throw "LeanFlow: expected one output word"
  | _ => throw "LeanFlow: expected one scalar output"

end LeanFlow.Graph

open Lean Elab Command

/-- The artifact is read and parsed by Lean. The resulting pure data is what
    the kernel sees in subsequent evaluator theorems. -/
elab "import_pytorch_graph " path:str " as " identifier:ident : command => do
  let text ← IO.FS.readFile path.getString
  let program ← IO.ofExcept (LeanFlow.Graph.parse text)
  let name := (← getCurrNamespace) ++ identifier.getId
  liftCoreM <| addAndCompile (.defnDecl {
    name := name
    levelParams := []
    type := mkConst ``LeanFlow.Graph.Program
    value := toExpr program
    hints := .regular 0
    safety := .safe })
