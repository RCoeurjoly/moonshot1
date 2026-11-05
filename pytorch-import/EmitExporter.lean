import NN.Runtime.PyTorch.Export.TorchExport

def main : IO Unit :=
  IO.FS.writeFile "build/torchlean_export.py" (Export.PyTorch.TorchExport.script {})
