import Task2.Imported.BaselineAdapter
import Lean

open Task2 Task2.Imported.BaselineAdapter

/-- Test-only mutant of the observation function; the circuit transitions are real. -/
def mutant : Device := { Task2.Imported.baseline with
  result := fun s => s.observed.map (fun word => word ^^^ 1#32) }

def main (args : List String) : IO Unit := do
  let [destination] := args | throw (IO.userError "expected witness destination")
  let a : Words := fun i => BitVec.ofNat 32 (i.val+1)
  let b : Words := fun i => BitVec.ofNat 32 (16-i.val)
  let state := advance (witness a b) 436
  let some original := state.observed | throw (IO.userError "missing original payload")
  let some changed := mutant.result state | throw (IO.userError "missing mutant payload")
  unless original == 816#32 && changed == 817#32 do
    throw (IO.userError "mutation mismatch witness was not reproduced")
  let evidence := Lean.Json.mkObj [
    ("scope", Lean.toJson "test-only payload XOR 1; concrete counterexample only"),
    ("edges", Lean.toJson (436 : Nat)), ("expected", Lean.toJson (816 : Nat)),
    ("original", Lean.toJson original.toNat), ("mutant", Lean.toJson changed.toNat),
    ("input_words", Lean.toJson [((List.finRange 16).map (fun i => (a i).toNat)),
                                  ((List.finRange 16).map (fun i => (b i).toNat))])]
  IO.FS.writeFile destination (evidence.pretty ++ "\n")
  IO.println "TASK2_MUTANT_COUNTEREXAMPLE expected=816 original=816 mutant=817 edges=436"
