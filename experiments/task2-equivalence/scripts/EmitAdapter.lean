import NN.Runtime.PyTorch.Export.TorchExport

def main (args : List String) : IO Unit := do
  let [path] := args | throw (IO.userError "expected destination for pinned TorchLean adapter")
  IO.FS.writeFile path (Export.PyTorch.TorchExport.script {})
