#!/usr/bin/env python3
"""Strict integer-dot adapter for the captured TorchLean v2 graph.

The Python evaluator is a differential control. Task2.Source supplies the Lean semantics.
Unknown operators, shapes, effects and dtype conversions are rejected.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


def validate_graph(graph):
    if graph.get("format") != "torchlean.ir.v2" or graph.get("frontend") != "pytorch":
        raise ValueError("unsupported graph format/frontend")
    if graph.get("capture_constraints") != [] or graph.get("input_ids") != [0, 1] or graph.get("output_ids") != [2]:
        raise ValueError("unsupported graph interface or constraints")
    nodes = graph.get("nodes", [])
    if len(nodes) != 3:
        raise ValueError("unsupported graph node count")
    for i, node in enumerate(nodes):
        expected = {"id": i, "kind": "input" if i < 2 else "matmul",
                    "parents": [] if i < 2 else [0, 1], "shape": [16] if i < 2 else [],
                    "dtype": {"kind": "integer", "signed": True, "width": 32}, "value_kind": "tensor"}
        if any(node.get(k) != v for k, v in expected.items()) or set(node) - set(expected) - {"debug_target"}:
            raise ValueError(f"unsupported node {i}: {node}")
    if set(graph) - {"format", "frontend", "capture_constraints", "input_ids", "output_ids", "nodes"}:
        raise ValueError("unsupported graph metadata")


def evaluate_words(graph, a, b):
    validate_graph(graph)
    if len(a) != 16 or len(b) != 16 or any(type(w) is not int or not 0 <= w < 2**32 for w in a + b):
        raise ValueError("expected sixteen complete 32-bit words per input")
    accumulator = 0
    for x, y in zip(a, b):
        accumulator = (accumulator + x * y) % 2**32
    return accumulator


def emit_program(graph, destination):
    validate_graph(graph)
    sha = hashlib.sha256(json.dumps(graph, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    rows = []
    for n in graph["nodes"]:
        parents = "#[" + ", ".join(map(str, n["parents"])) + "]"
        shape = "[" + ", ".join(map(str, n["shape"])) + "]"
        rows.append(f'    {{ id := {n["id"]}, parents := {parents}, kind := .{n["kind"]}, outShape := {shape} }}')
    text = 'import NN.IR.Program\n\nnamespace Task2.Imported\n'
    text += f'def graphIdentity : String := "{sha}"\n'
    text += 'def sourceProgram : NN.IR.Program where\n  graph := { nodes := #[\n'
    text += ",\n".join(rows) + '\n  ] }\n'
    text += '  dtypes := #[.integer true (some 32), .integer true (some 32), .integer true (some 32)]\n'
    text += '  inputs := #[0, 1]\n  outputs := #[2]\n  primitives := #[none, none, none]\n'
    text += 'end Task2.Imported\n'
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)


def capture(manifest, adapter_script, out):
    """Run in the original Python environment, retaining the original export flags."""
    import torch
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    os.environ["MATMUL_PY"] = manifest["artifacts"]["model"]["path"]
    source_command = manifest["source_build_command"]
    import re
    match = re.search(r'export PYTHONPATH="([^"$]+)', source_command)
    if not match:
        raise ValueError("cannot recover original adapter Python path")
    sys.path[:0] = [p for p in match[1].split(":") if p]
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    adapter = load("task2_model_adapter", manifest["artifacts"]["adapter"]["path"])
    model = adapter.build_model(None).eval()
    examples = tuple(adapter.example_inputs())
    exported = torch.export.export(model, examples, strict=getattr(adapter, "EXPORT_STRICT", True))
    torch.export.save(exported, out / "reference.pt2")
    (out / "exported-graph.txt").write_text(str(exported.graph))
    bridge = load("torchlean_capture", adapter_script)
    # Consume this exact ExportedProgram, avoiding a second export with different flags.
    old_export = torch.export.export
    torch.export.export = lambda *args, **kwargs: exported
    try:
        bridge.export_torchlean_graph_json(model, examples, str(out / "reference.json"), require_torch_export=True)
    finally:
        torch.export.export = old_export
    graph = json.loads((out / "reference.json").read_text())
    validate_graph(graph)
    from torch_mlir.fx import export_and_import
    original_mlir = Path(manifest["artifacts"]["torch"]["path"]).read_text()
    captured_mlir = str(export_and_import(exported, output_type="torch"))
    (out / "recaptured-torch.mlir").write_text(captured_mlir)
    if captured_mlir != original_mlir:
        raise ValueError("derived export does not reproduce the original compiler input")
    cases = [([], [], 0), ([0xfffffffe], [3], 0xfffffffa),
             ([0x80000000], [0xffffffff], 0x80000000),
             ([0x7fffffff], [2], 0xfffffffe),
             ([0x7fffffff, 1], [1, 1], 0x80000000),
             ([0xffffffff, 1], [1, 1], 0)]
    results = []
    for a, b, expected in cases:
        a += [0] * (16-len(a)); b += [0] * (16-len(b))
        signed = lambda words: [w if w < 2**31 else w - 2**32 for w in words]
        got = int(model(torch.tensor(signed(a), dtype=torch.int32), torch.tensor(signed(b), dtype=torch.int32)).item()) % 2**32
        local = evaluate_words(graph, a, b)
        if got != expected or local != expected:
            raise ValueError(f"word parity failed: expected {expected}, PyTorch {got}, local {local}")
        results.append({"input_words": [a, b], "expected_output_words": [[expected]], "pytorch": got, "local": local})
    (out / "word-controls.json").write_text(json.dumps(results, indent=2) + "\n")
    emit_program(graph, out.parent / "generated/Task2/Imported/Source.lean")
    print(json.dumps({"status": "passed_control", "cases": len(results), "compiler_input_bytes_equal": True,
                      "pytorch_version": torch.__version__}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--adapter-script", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    capture(json.loads(args.manifest.read_text()), args.adapter_script, args.out)


if __name__ == "__main__":
    main()
