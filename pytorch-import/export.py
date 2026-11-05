from pathlib import Path
import sys
import torch
from model import MatmulModule

# This exporter is emitted from the pinned TorchLean library by EmitExporter.lean.
sys.path.insert(0, str(Path(__file__).resolve().parent / "build"))
from torchlean_export import export_torchlean_graph_json

model = MatmulModule().eval()
inputs = (torch.zeros(16, dtype=torch.int32), torch.zeros(16, dtype=torch.int32))
export_torchlean_graph_json(model, inputs, "model.json", require_torch_export=True)
print("PyTorch graph exported to model.json")
