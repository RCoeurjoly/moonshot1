import NN.Runtime.IR

def main (args : List String) : IO Unit := do
  let text ← IO.FS.readFile (args.headD "model.json")
  let artifact ← IO.ofExcept (Lean.Json.parse text)
  -- This is TorchLean's own importer; it also checks shapes and element types.
  let program : NN.IR.Program ← IO.ofExcept (Import.IR.parseProgram artifact)
  IO.println "Imported successfully into TorchLean as NN.IR.Program:"
  IO.println (reprStr program)
