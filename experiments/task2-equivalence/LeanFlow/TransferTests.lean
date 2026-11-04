import LeanFlow.Bridge

open LeanFlow

private def sameValue : SMT.Value → SMT.Value → Bool
  | .bits width word, other => match other.asBits width with | .ok value => word == value | _ => false
  | .boolean word, other => match other.asBool with | .ok value => word == value | _ => false
  | .memory address width read, other =>
    match other.asMemory address width with
    | .ok other => (List.range (2^address)).all fun index =>
      read (BitVec.ofNat address index) == other (BitVec.ofNat address index)
    | _ => false

private def sameRecord (a b : Array SMT.Value) : Bool :=
  a.size == b.size && (a.zipWith sameValue b).all id

def main : IO Unit := do
  for seed in [0,1,4294967295] do
    let state := Bridge.testState seed
    for flag in [0,1,21,42,63] do
      let inputs : Bridge.CoreInputs :=
        { i0 := BitVec.ofNat 1 flag, i1 := BitVec.ofNat 1 (flag/2),
          i2 := BitVec.ofNat 1 (flag/4), i3 := BitVec.ofNat 1 (flag/8),
          i4 := BitVec.ofNat 1 (flag/16), i5 := BitVec.ofNat 1 (flag/32) }
      let (outputs,nextState) ← IO.ofExcept (Bridge.transfer inputs state)
      let expected := Task2.Imported.BaselineCore.evaluate inputs state
      unless sameRecord (Bridge.encodeOutputs outputs) (Bridge.encodeOutputs expected.outputs) &&
          sameRecord (Bridge.encodeState nextState) (Bridge.encodeState expected.nextState) do
        throw (IO.userError s!"full SMT transition differs: seed {seed}, flags {flag}")
  IO.println "LEAN_TRANSFER_TESTS passed: all outputs, all 453 state fields, all memory words; 15 cases"
