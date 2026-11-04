#!/usr/bin/env python3
"""Export the frozen PyTorch model to JSON. No Lean or SMT models are emitted."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import types

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'build/lean-flow/pytorch.json')
    args = parser.parse_args()
    provider = json.loads((ROOT/'reports/reference/source-provenance.json').read_text())
    original_python = Path(provider['python_environment'])/'bin/python3'
    if Path(sys.executable).resolve() != original_python.resolve():
        os.execv(original_python, [str(original_python), str(Path(__file__).resolve()), *sys.argv[1:]])
    for key in ['model', 'adapter']:
        info = provider['artifacts'][key]
        if hashlib.sha256(Path(info['path']).read_bytes()).hexdigest() != info['sha256']:
            raise ValueError(f'frozen {key} identity changed')
    os.environ['MATMUL_PY'] = provider['artifacts']['model']['path']
    original_path = re.search(r'export PYTHONPATH="([^"$]+)', provider['source_build_command'])
    if original_path is None:
        raise ValueError('missing frozen model adapter search path')
    sys.path[:0] = [p for p in original_path[1].split(':') if p]
    import torch
    adapter = load('frozen_model_adapter', provider['artifacts']['adapter']['path'])
    model = adapter.build_model(None).eval()
    examples = tuple(adapter.example_inputs())
    exported = torch.export.export(model, examples, strict=getattr(adapter, 'EXPORT_STRICT', True))
    capture = types.ModuleType('pinned_torchlean_capture')
    bridge = ROOT/'reports/reference/capture_bridge-torchlean-adapter.py.gz'
    exec(compile(gzip.decompress(bridge.read_bytes()), str(bridge), 'exec'), capture.__dict__)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    original_export = torch.export.export
    torch.export.export = lambda *a, **kw: exported
    try:
        capture.export_torchlean_graph_json(model, examples, str(args.out), require_torch_export=True)
    finally:
        torch.export.export = original_export
    print(f'PYTORCH_GRAPH_EXPORTED {args.out}')


if __name__ == '__main__':
    main()
