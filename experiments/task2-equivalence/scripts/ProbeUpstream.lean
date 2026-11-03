import NN.Runtime.IR

def main (args : List String) : IO Unit := do
  let [graphPath, controlsPath] := args | throw (IO.userError "expected graph and controls")
  let artifact ← IO.ofExcept (Lean.Json.parse (← IO.FS.readFile graphPath))
  let program ← IO.ofExcept (Import.IR.parseProgram artifact)
  let controls ← IO.ofExcept (Lean.Json.parse (← IO.FS.readFile controlsPath))
  let cases ← IO.ofExcept controls.getArr?
  let words ← IO.ofExcept (cases[0]!.getObjValAs? (Array (Array Nat)) "input_words")
  let mut inputs := #[]
  for index in [:program.inputs.size] do
    let id := program.inputs[index]!
    let node ← IO.ofExcept (program.graph.getNode id)
    let dtype ← IO.ofExcept (program.dtype id)
    inputs := inputs.push (← IO.ofExcept (NN.IR.Reference.load dtype node.outShape words[index]!))
  let payload ← IO.ofExcept (Import.IR.parsePayload NN.IR.Interpreter.reference NN.IR.Reference.load artifact)
  let _ ← IO.ofExcept (NN.IR.Interpreter.eval NN.IR.Interpreter.reference program payload inputs)
  IO.println "Upstream integer evaluation succeeded"
