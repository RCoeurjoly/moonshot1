import LeanFlow.SMT

/- This Lean program only generates record plumbing. The generated universal
   theorem must still be checked by Lean's kernel. It supplies no axioms. -/
open LeanFlow.SMT

private def encode (sort : Ty) (term : String) : String :=
  match sort with
  | .bits width => s!".bits {width} ({term})"
  | .boolean => s!".boolean ({term})"
  | .memory address width => s!".memory {address} {width} ({term})"

private def decode (sort : Ty) (values : String) (index : Nat) : String :=
  match sort with
  | .bits width => s!"(← SMT.bitsAt {width} {values} {index})"
  | .boolean => s!"(← (← SMT.valueAt {values} {index}).asBool)"
  | .memory address width => s!"(← SMT.memoryAt {address} {width} {values} {index})"

def main : IO Unit := do
  let program ← IO.ofExcept (parse (← IO.FS.readFile "build/lean-flow/accelerator.smt2"))
  let list (values : Array String) := String.intercalate ", " values.toList
  let enc (fields : Array Field) (field : Nat → String) :=
    "#[" ++ list (fields.mapIdx fun i f => encode f.sort (field i)) ++ "]"
  let stateField (i : Nat) := s!"state.g{i/128}.s{i}"
  let outputFields := program.outputs.mapIdx fun i f => s!"o{i} := {decode f.sort "values" i}"
  let groups := (List.range ((program.states.size+127)/128)).map fun group =>
    let indices := (List.range program.states.size).filter (fun i => i/128 == group)
    let fields := indices.map fun i => s!"s{i} := {decode program.states[i]!.sort "values" i}"
    s!"g{group} := \{ " ++ String.intercalate ", " fields ++ " }"
  let seedGroups := (List.range ((program.states.size+127)/128)).map fun group =>
    let indices := (List.range program.states.size).filter (fun i => i/128 == group)
    let fields := indices.map fun i =>
      let value := match program.states[i]!.sort with
        | .bits width => s!"BitVec.ofNat {width} (seed * {2654435761+i*7919})"
        | .boolean => s!"decide (seed % 2 = 0)"
        | .memory _ width => s!"fun address => BitVec.ofNat {width} (seed * {i+1} + address.toNat * 4294967295)"
      s!"s{i} := ({value})"
    s!"g{group} := \{ " ++ String.intercalate ", " fields ++ " }"
  let source := "import LeanFlow.SMTArtifact\nimport Task2.Imported.BaselineCore\nimport Task2.ProofTools\n\n" ++
    "set_option maxRecDepth 65536\nset_option maxHeartbeats 0\nnamespace LeanFlow\nnamespace Bridge\n" ++
    "abbrev CoreInputs := Task2.Imported.BaselineCore.Inputs\n" ++
    "abbrev CoreState := Task2.Imported.BaselineCore.State\n" ++
    "abbrev CoreOutputs := Task2.Imported.BaselineCore.Outputs\n" ++
    "def encodeInputs (inputs : CoreInputs) : Array SMT.Value :=\n  " ++ enc program.inputs (fun i => s!"inputs.i{i}") ++ "\n" ++
    "def encodeState (state : CoreState) : Array SMT.Value :=\n  " ++ enc program.states stateField ++ "\n" ++
    "def encodeOutputs (outputs : CoreOutputs) : Array SMT.Value :=\n  " ++ enc program.outputs (fun i => s!"outputs.o{i}") ++ "\n" ++
    "def decodeOutputs (values : Array SMT.Value) : Except String CoreOutputs := do\n  pure { " ++ list outputFields ++ " }\n" ++
    "def decodeState (values : Array SMT.Value) : Except String CoreState := do\n  pure { " ++ String.intercalate ", " groups ++ " }\n" ++
    "def testState (seed : Nat) : CoreState :=\n  { " ++ String.intercalate ", " seedGroups ++ " }\n" ++
    "def transferFor (hardware : SMT.Program) (inputs : CoreInputs) (state : CoreState) : Except String (CoreOutputs × CoreState) := do\n" ++
    "  let result ← SMT.eval hardware (encodeInputs inputs) (encodeState state)\n" ++
    "  pure (← decodeOutputs result.outputs, ← decodeState result.nextState)\n" ++
    "def transfer := transferFor accelerator\n" ++
    "end Bridge\nend LeanFlow\n"
  IO.FS.createDirAll "build/lean-flow/library/LeanFlow"
  IO.FS.writeFile "build/lean-flow/library/LeanFlow/Bridge.lean" source
  IO.println s!"LEAN_RECORD_BRIDGE_GENERATED {program.states.size} state fields"
