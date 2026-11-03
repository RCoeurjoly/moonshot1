import Task2.Hardware
import Lean

namespace Task2.Trace

structure Frame where
  cycle : Nat
  reset : Bool
  start : Bool
  startReady : Bool
  tokenValid : Bool
  doneReady : Bool
  payloadValid : Bool
  payloadReady : Bool
  data : Word

structure Harness where
  State : Type
  seed : Words → Words → State
  step : State → State
  sample : State → Frame
  memoryA : State → BitVec 4 → Word
  memoryB : State → BitVec 4 → Word

def Frame.toJson (f : Frame) : Lean.Json :=
  let bit (b : Bool) : Lean.Json := Lean.toJson (if b then (1 : Nat) else 0)
  Lean.Json.mkObj [
    ("cycle", Lean.toJson f.cycle), ("rising", Lean.toJson true), ("reset", bit f.reset),
    ("in3_valid", bit f.start), ("in3_ready", bit f.startReady), ("out0_valid", bit f.tokenValid),
    ("in2_st0_done_ready", bit f.doneReady), ("in2_st0_valid", bit f.payloadValid),
    ("in2_st0_ready", bit f.payloadReady), ("in2_st0", Lean.toJson f.data.toNat)]

/-- Concrete correspondence controls only; this finite runner is not Implements. -/
def runControls (h : Harness) (args : List String) : IO Unit := do
  let [requestPath, outputPath] := args | throw (IO.userError "expected word controls and trace destination")
  let request ← IO.ofExcept (Lean.Json.parse (← IO.FS.readFile requestPath))
  let mut cases ← IO.ofExcept request.getArr?
  let sampleA := (List.range 16).map (· + 1)
  let sampleB := (List.range 16).map (16 - ·)
  cases := cases.push (Lean.Json.mkObj [
    ("input_words", Lean.toJson [sampleA, sampleB]),
    ("expected_output_words", Lean.toJson ([[816]] : List (List Nat)))])
  let mut results : Array Lean.Json := #[]
  for caseIndex in [:cases.size] do
    let words ← IO.ofExcept (cases[caseIndex]!.getObjValAs? (Array (Array Nat)) "input_words")
    let expected ← IO.ofExcept (cases[caseIndex]!.getObjValAs? (Array (Array Nat)) "expected_output_words")
    unless words.size == 2 && words.all (fun row => row.size == 16 && row.all (· < 2^32)) &&
        expected.size == 1 && (expected[0]!).size == 1 do
      throw (IO.userError "invalid complete-word control")
    let a : Words := fun i => BitVec.ofNat 32 (words[0]!)[i.val]!
    let b : Words := fun i => BitVec.ofNat 32 (words[1]!)[i.val]!
    let mut state := h.seed a b
    let mut trace : Array Lean.Json := #[]
    let mut resetPreserved := false
    let mut found : Option (Nat × Nat) := none
    -- This is a simulation budget, not a proved completion bound.
    for cycle in [:10000] do
      let frame := h.sample state
      trace := trace.push frame.toJson
      state := h.step state
      if cycle == 3 then
        resetPreserved := (List.finRange 16).all fun i =>
          h.memoryA state (BitVec.ofNat 4 i.val) == a i &&
          h.memoryB state (BitVec.ofNat 4 i.val) == b i
      if !frame.reset && frame.payloadValid && frame.payloadReady then
        found := some (cycle + 1, frame.data.toNat)
        break
    let some (edges, result) := found | throw (IO.userError "hardware control timed out without an accepted payload")
    unless result == (expected[0]!)[0]! && resetPreserved do
      throw (IO.userError s!"hardware word/reset control failed in case {caseIndex}: {result}")
    results := results.push (Lean.Json.mkObj [
      ("case", Lean.toJson caseIndex), ("edges", Lean.toJson edges), ("result", Lean.toJson result),
      ("ram_reset_preserved", Lean.toJson resetPreserved), ("trace", Lean.Json.arr trace)])
  IO.FS.writeFile outputPath ((Lean.Json.arr results).pretty ++ "\n")
  IO.println s!"TASK2_HARDWARE_CONTROLS {results.size} passed (concrete traces only)"

end Task2.Trace
