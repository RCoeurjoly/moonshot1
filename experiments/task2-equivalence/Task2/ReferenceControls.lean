import Task2.Source
import NN.Runtime.IR

def main (args : List String) : IO Unit := do
  let [graphPath, controlsPath] := args
    | throw (IO.userError "expected graph and controls JSON")
  let graph ← IO.ofExcept (Lean.Json.parse (← IO.FS.readFile graphPath))
  let parsed ← IO.ofExcept (Import.IR.parseProgram graph)
  unless reprStr parsed == reprStr Task2.Imported.sourceProgram do
    throw (IO.userError "pure imported Program differs from TorchLean typed import")
  let controls ← IO.ofExcept (Lean.Json.parse (← IO.FS.readFile controlsPath))
  let cases ← IO.ofExcept controls.getArr?
  for request in cases do
    let words ← IO.ofExcept (request.getObjValAs? (Array (Array Nat)) "input_words")
    unless words.size == 2 && words.all (·.size == 16) do
      throw (IO.userError "expected two vectors of sixteen words")
    let a : Task2.Words := fun i => BitVec.ofNat 32 (words[0]!)[i.val]!
    let b : Task2.Words := fun i => BitVec.ofNat 32 (words[1]!)[i.val]!
    let result ← IO.ofExcept (Task2.sourceEval a b)
    let expected ← IO.ofExcept (request.getObjValAs? (Array (Array Nat)) "expected_output_words")
    unless expected == #[#[result.toNat]] do
      throw (IO.userError s!"Lean word control mismatch: {result.toNat}, expected {expected}")
  IO.println s!"TASK2_REFERENCE_CONTROLS {cases.size} passed; typed Program agrees"

#print axioms Task2.source_agrees
