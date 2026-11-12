import Task2RTL
import Lean.Data.Json

/-! Concrete controls execute the same native model checked by the universal proof. -/
open Lean

private def resetEdges := 4
private def edgeLimit := 1000

private def traceHeader :=
  "cycle,reset,in3_valid,in3_ready,out0_valid,in2_st0_done_ready,in2_st0_valid,in2_st0_ready,in2_st0\n"

private def inputsFor (a b : Array Nat) (reset start : BitVec 1) : Task2RTL.Inputs :=
  { clock := 0, reset, in3_valid := start
    out0_ready := 1, in2_st0_ready := 1, in2_st0_done_valid := 0
    ram_a_0 := BitVec.ofNat 32 a[0]!
    ram_a_1 := BitVec.ofNat 32 a[1]!
    ram_a_2 := BitVec.ofNat 32 a[2]!
    ram_a_3 := BitVec.ofNat 32 a[3]!
    ram_a_4 := BitVec.ofNat 32 a[4]!
    ram_a_5 := BitVec.ofNat 32 a[5]!
    ram_a_6 := BitVec.ofNat 32 a[6]!
    ram_a_7 := BitVec.ofNat 32 a[7]!
    ram_a_8 := BitVec.ofNat 32 a[8]!
    ram_a_9 := BitVec.ofNat 32 a[9]!
    ram_a_10 := BitVec.ofNat 32 a[10]!
    ram_a_11 := BitVec.ofNat 32 a[11]!
    ram_a_12 := BitVec.ofNat 32 a[12]!
    ram_a_13 := BitVec.ofNat 32 a[13]!
    ram_a_14 := BitVec.ofNat 32 a[14]!
    ram_a_15 := BitVec.ofNat 32 a[15]!
    ram_b_0 := BitVec.ofNat 32 b[0]!
    ram_b_1 := BitVec.ofNat 32 b[1]!
    ram_b_2 := BitVec.ofNat 32 b[2]!
    ram_b_3 := BitVec.ofNat 32 b[3]!
    ram_b_4 := BitVec.ofNat 32 b[4]!
    ram_b_5 := BitVec.ofNat 32 b[5]!
    ram_b_6 := BitVec.ofNat 32 b[6]!
    ram_b_7 := BitVec.ofNat 32 b[7]!
    ram_b_8 := BitVec.ofNat 32 b[8]!
    ram_b_9 := BitVec.ofNat 32 b[9]!
    ram_b_10 := BitVec.ofNat 32 b[10]!
    ram_b_11 := BitVec.ofNat 32 b[11]!
    ram_b_12 := BitVec.ofNat 32 b[12]!
    ram_b_13 := BitVec.ofNat 32 b[13]!
    ram_b_14 := BitVec.ofNat 32 b[14]!
    ram_b_15 := BitVec.ofNat 32 b[15]!
  }

private def simulate (a b : Array Nat) : IO String := do
  let mut state := Task2RTL.initialState
  let mut start : BitVec 1 := 0
  let mut trace := traceHeader
  for cycle in [:edgeLimit] do
    let reset : BitVec 1 := if cycle < resetEdges then 1 else 0
    let evaluation := Task2RTL.evaluate (inputsFor a b reset start) state
    let out := evaluation.outputs
    trace := trace ++ s!"{cycle},{reset.toNat},{start.toNat},{out.in3_ready.toNat},{out.out0_valid.toNat},{out.in2_st0_done_ready.toNat},{out.in2_st0_valid.toNat},1,{out.in2_st0.toNat}\n"
    if reset == 0 && out.in2_st0_valid != 0 then return trace
    state := evaluation.nextState
    start := if reset != 0 then 1 else if out.in3_ready != 0 then 0 else start
  throw (IO.userError "native Sparkle model did not complete within 1000 edges")

def main (args : List String) : IO Unit := do
  let [controls, output] := args
    | throw (IO.userError "usage: native-traces controls.json output-dir")
  let requests ← IO.ofExcept (Json.parse (← IO.FS.readFile controls))
  let requests ← IO.ofExcept requests.getArr?
  for (request, index) in requests.zipIdx do
    let words ← IO.ofExcept (request.getObjValAs? (Array (Array Nat)) "input_words")
    unless words.size == 2 && words[0]!.size == 16 && words[1]!.size == 16 do
      throw (IO.userError "expected two length-16 input vectors")
    IO.FS.writeFile (System.FilePath.mk output / s!"case-{index}-lean.csv")
      (← simulate words[0]! words[1]!)
    IO.println s!"NATIVE_LEAN_TRACE {index} complete"
