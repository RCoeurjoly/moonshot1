import NativeExport

export_native_sparkle "tests/fixtures/native_counter.sv" as NativeCounter
  into "build/native-smoke"

export_native_sparkle "tests/fixtures/wide_registers.sv" as WideRegisters
  into "build/native-smoke"

private def inputs (a b : BitVec 8) (reset : BitVec 1 := 0) : NativeCounter.Inputs :=
  { clock := 1, reset, a, b }

example (a b : BitVec 8) :
    (NativeCounter.evaluate (inputs a b) NativeCounter.initialState).outputs.sum = a + b := by
  rfl

example (a b : BitVec 8) :
    (NativeCounter.evaluate (inputs a b) NativeCounter.initialState).outputs.less =
      (if a.slt b then 1 else 0) := by
  rfl

example :
    (NativeCounter.evaluate (inputs 255 1) NativeCounter.initialState).outputs.sum = 0 := by
  decide

def main : IO Unit := do
  let initial := NativeCounter.initialState
  let reset := (NativeCounter.evaluate (inputs 0 0 1) initial).nextState
  let next := (NativeCounter.evaluate (inputs 0 0) reset).nextState
  let out := (NativeCounter.evaluate (inputs 0 0) next).outputs
  if out.count != 1 then throw (IO.userError "native Sparkle reset/counter mismatch")
  let wide := WideRegisters.evaluate { clock := 0, reset := 1 } WideRegisters.initialState
  let wide := WideRegisters.evaluate { clock := 0, reset := 0 } wide.nextState
  let wide := WideRegisters.evaluate { clock := 0, reset := 0 } wide.nextState
  if wide.outputs.q != BitVec.allOnes 64 then
    throw (IO.userError "native Sparkle grouped state mismatch")
  IO.println "PASS: upstream Sparkle reflection, symbolic addition/signed comparison, overflow, reset, grouped register storage"
