import sys
import torch

class MatmulModule(torch.nn.Module):
    def forward(self, a, b):
        return torch.matmul(a, b)

if __name__ == "__main__":
    from torchlean_export import export_torchlean_graph_json

    inputs = tuple(torch.zeros(16, dtype=torch.int32) for _ in range(2))
    export_torchlean_graph_json(
        MatmulModule().eval(), inputs, sys.argv[1], require_torch_export=True
    )
