"""Boundary tests: stale artifacts, changed interfaces and false proof verdicts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]


class ExperimentTests(unittest.TestCase):
    def hardware(self):
        path = ROOT / "scripts/import_hardware.py"
        self.assertTrue(path.exists(), "hardware importer has not been implemented")
        spec = importlib.util.spec_from_file_location("hardware_importer", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def reference(self):
        path = ROOT / "scripts/import_reference.py"
        self.assertTrue(path.exists(), "integer reference importer has not been implemented")
        spec = importlib.util.spec_from_file_location("reference_importer", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def reference_graph(self):
        dtype = {"kind": "integer", "signed": True, "width": 32}
        return {"format": "torchlean.ir.v2", "frontend": "pytorch", "capture_constraints": [],
                "input_ids": [0, 1], "output_ids": [2], "nodes": [
                    {"id": 0, "kind": "input", "parents": [], "shape": [16], "dtype": dtype, "value_kind": "tensor"},
                    {"id": 1, "kind": "input", "parents": [], "shape": [16], "dtype": dtype, "value_kind": "tensor"},
                    {"id": 2, "kind": "matmul", "parents": [0, 1], "shape": [], "dtype": dtype, "value_kind": "tensor"}]}

    def runner(self):
        path = ROOT / "scripts/run.py"
        self.assertTrue(path.exists(), "attachment runner has not been implemented")
        spec = importlib.util.spec_from_file_location("experiment_runner", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fixture(self, root):
        files = {
            "model": "class MatmulModule: pass\n",
            "adapter": "# adapter provenance\n",
            "torch": "module { func.func @main(%arg0: !torch.vtensor<[16],si32>, %arg1: !torch.vtensor<[16],si32>) -> !torch.vtensor<[],si32> { } }\n",
            "sim": '{"status":"PASS","expected":816,"got":816}\n',
        }
        for name, contents in files.items():
            (root / name).write_text(contents)
        sv = root / "sv"
        sv.mkdir()
        (sv / "main.sv").write_text("module main; endmodule\n")
        (sv / "sources.f").write_text(str(sv / "main.sv") + "\n")
        graph = {}
        for name, output in [("matmul-torch.mlir", "torch"), ("matmul-sv", "sv"), ("matmul-sv-sim.json", "sim")]:
            graph[str(root / (name + ".drv"))] = {
                "env": {"name": name, "buildCommand": "", "buildInputs": ""},
                "outputs": {"out": {"path": str(root / output)}},
            }
        graph[str(root / "matmul-torch.mlir.drv")]["env"].update(
            buildInputs="/nix/store/example-python-env",
            buildCommand=f'export MATMUL_PY="{root / "model"}"\npython compile.py --adapter {root / "adapter"} --out "$out"\n',
        )
        return graph

    def test_attached_task2_interface(self):
        """Catches scalar/matrix or signed-width drift in the compiler input."""
        runner = self.runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            graph = self.fixture(root)
            manifest = runner.assemble_manifest(graph)
            self.assertEqual(manifest["interface"], {
                "inputs": [{"shape": [16], "dtype": "int32"}] * 2,
                "output": {"shape": [], "dtype": "int32"},
            })
            self.assertEqual(manifest["artifacts"]["torch"]["derivation"], str(root / "matmul-torch.mlir.drv"))
            self.assertEqual(manifest["simulation"]["status"], "PASS")
            (root / "torch").write_text('func.func @forward(%a: !torch.vtensor<[16],f32>, %b: !torch.vtensor<[16],f32>) -> !torch.vtensor<[],f32>')
            with self.assertRaisesRegex(ValueError, "interface"):
                runner.assemble_manifest(graph)

    def test_stale_reference_is_rejected(self):
        """Catches reusing evidence after the referenced file changes."""
        runner = self.runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = runner.assemble_manifest(self.fixture(root))
            runner.verify_manifest(manifest)
            (root / "model").write_text("changed operation\n")
            with self.assertRaisesRegex(ValueError, "identity"):
                runner.verify_manifest(manifest)

    def test_mismatched_artifact_cannot_reuse_verdict(self):
        """A previously proved status must not bypass a changed RTL identity."""
        runner=self.runner()
        self.assertTrue(hasattr(runner,"check"),"hardware proof stage is missing")
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);manifest=runner.assemble_manifest(self.fixture(root))
            (root/"manifest.json").write_text(json.dumps(manifest))
            (root/"sv/main.sv").write_text("module main; wire changed = 1; endmodule\n")
            with self.assertRaisesRegex(ValueError,"identity"):
                runner.check(SimpleNamespace(out=root,design="baseline",timeout=600,workers=4))

    def test_reference_word_parity(self):
        """Catches signed conversion, missing modular reduction and skipped terms."""
        ref = self.reference()
        graph = self.reference_graph()
        cases = [([], [], 0), ([0xfffffffe], [3], 0xfffffffa),
                 ([0x80000000], [0xffffffff], 0x80000000),
                 ([0x7fffffff], [2], 0xfffffffe),
                 ([0x7fffffff, 1], [1, 1], 0x80000000),
                 ([0xffffffff, 1], [1, 1], 0)]
        for a, b, expected in cases:
            with self.subTest(a=a, b=b):
                self.assertEqual(ref.evaluate_words(graph, a + [0] * (16-len(a)), b + [0] * (16-len(b))), expected)

    def test_reference_rejects_changed_operation(self):
        """Catches an importer that silently treats any graph as a dot product."""
        ref = self.reference()
        graph = self.reference_graph()
        graph["nodes"][2]["kind"] = "add"
        with self.assertRaisesRegex(ValueError, "unsupported"):
            ref.evaluate_words(graph, [0] * 16, [0] * 16)

    def test_axiom_audit_rejects_equivalence_assumption(self):
        """Catches accepting a solver verdict or desired equivalence as an axiom."""
        runner = self.runner()
        self.assertTrue(hasattr(runner, "audit_axioms"), "axiom audit has not been implemented")
        self.assertEqual(runner.audit_axioms("'Task2.source_agrees' depends on axioms: [propext, Classical.choice, Quot.sound]", "Task2.source_agrees"), ["propext", "Classical.choice", "Quot.sound"])
        with self.assertRaisesRegex(ValueError, "undeclared axiom"):
            runner.audit_axioms("'Task2.source_agrees' depends on axioms: [Task2.assumed_equivalent]", "Task2.source_agrees")
        with self.assertRaisesRegex(ValueError, "audit"):
            runner.audit_axioms("Build completed successfully", "Task2.source_agrees")

    def test_timeout_is_inconclusive(self):
        """Catches treating a stopped process as a proof."""
        runner = self.runner()
        with tempfile.TemporaryDirectory() as td:
            result = runner.execute([sys.executable, "-c", "import time; time.sleep(30)"], Path(td) / "timeout.log", timeout=0.1)
            self.assertEqual(result["status"], "timeout")
            self.assertIsNone(result["returncode"])
            self.assertIn("sha256", result["log"])

    def test_solver_failure_is_not_counterexample(self):
        """Catches treating a tool error or success exit alone as a formal verdict."""
        runner = self.runner()
        with tempfile.TemporaryDirectory() as td:
            result = runner.execute([sys.executable, "-c", "raise SystemExit(2)"], Path(td) / "failure.log")
            self.assertEqual(result["status"], "failed")
            result = runner.execute([sys.executable, "-c", "print('PASS')"], Path(td) / "success.log")
            self.assertEqual(result["status"], "prepared")

    def test_process_peak_memory_is_measured(self):
        """Catches absent or cumulative memory measurement in benchmark evidence."""
        runner = self.runner()
        with tempfile.TemporaryDirectory() as td:
            result = runner.execute([sys.executable, "-c", "a=bytearray(8*1024*1024)"], Path(td) / "memory.log")
            self.assertIsInstance(result["peak_rss_kib"], int)
            self.assertGreater(result["peak_rss_kib"], 8192)

    def test_payload_event_selection(self):
        """Catches treating the control token, reset output or stalled payload as a result."""
        hardware = self.hardware()
        row = {"rising": True, "reset": 0, "out0_valid": 1, "in2_st0_valid": 0,
               "in2_st0_ready": 1, "in2_st0": 123}
        self.assertIsNone(hardware.payload_event(row))
        row.update(out0_valid=0, in2_st0_valid=1)
        self.assertEqual(hardware.payload_event(row), 123)
        for field in ["reset", "in2_st0_ready", "rising"]:
            other = dict(row)
            other[field] = 1 if field == "reset" else 0
            self.assertIsNone(hardware.payload_event(other))

    def test_zero_write_ports_is_not_an_asynchronous_write(self):
        """Catches falsely rejecting read-only input RAM, without permitting real async writes."""
        hardware = self.hardware()
        self.assertTrue(hasattr(hardware, "preflight"), "zero-port adapter has not been implemented")
        module = {"ports": {"clock": {"direction": "input", "bits": [2]}}, "netnames": {}, "cells": {
            "input_ram": {"type": "$mem_v2", "attributes": {}, "connections": {"RD_CLK": [], "WR_CLK": []},
                          "parameters": {"SIZE": "10", "OFFSET": "0", "RD_PORTS": "0", "WR_PORTS": "0",
                                         "RD_CLK_ENABLE": "0", "WR_CLK_ENABLE": "0", "RD_CLK_POLARITY": "0", "WR_CLK_POLARITY": "0"}}}}
        result = hardware.preflight(module)
        self.assertEqual(result["memory_cells"], 1)
        # The real import metadata remains intact; normalization is only for preflight.
        self.assertEqual(module["cells"]["input_ram"]["parameters"]["WR_CLK_ENABLE"], "0")
        module["cells"]["input_ram"]["parameters"]["WR_PORTS"] = "1"
        module["cells"]["input_ram"]["connections"]["WR_CLK"] = ["x"]
        with self.assertRaisesRegex(ValueError, "Asynchronous memory writes"):
            hardware.preflight(module)

    def test_symbolic_ram_survives_reset(self):
        """Checks real Lean preservation theorems and an initial-state witness, not a zero-RAM trace."""
        path = ROOT / "build/generated/Task2/Imported/BaselineAdapter.lean"
        self.assertTrue(path.exists(), "imported memory proof adapter has not been generated")
        env = dict(os.environ)
        env["LEAN_PATH"] = str(ROOT / ".lake/build/lib/lean")
        completed = subprocess.run(["lean", str(path)], cwd=ROOT, env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        self.assertEqual(completed.returncode, 0, completed.stdout)
        for theorem in ("memoryA_preserved", "memoryB_preserved", "initial_exists"):
            self.runner().audit_axioms(completed.stdout, "Task2.Imported.BaselineAdapter." + theorem)

    def test_cycle_import_rejects_other_clock(self):
        """Catches applying single-clock formalff normalization without checking its assumption."""
        hardware = self.hardware()
        module = {"ports": {"clock": {"direction": "input", "bits": [2]}}, "netnames": {}, "cells": {
            "badff": {"type": "$dff", "attributes": {}, "parameters": {"CLK_POLARITY": "1", "WIDTH": "1"},
                      "connections": {"CLK": [9], "D": [5], "Q": [6]}}}}
        with self.assertRaisesRegex(ValueError, "positive-edge clock"):
            hardware.preflight(module)

    def test_hardware_trace_correspondence(self):
        """Catches cycle shifts, wrong payloads, and two equally stalled traces."""
        hardware = self.hardware()
        self.assertTrue(hasattr(hardware, "compare_traces"), "trace correspondence checker is missing")
        rows = [{"cycle": i, "rising": True, "reset": int(i < 4), "in3_valid": 1,
                 "in3_ready": 0, "in2_st0_ready": 1, "in2_st0_done_ready": 0,
                 "out0_valid": int(i == 4), "in2_st0_valid": int(i == 5), "in2_st0": 123} for i in range(6)]
        self.assertEqual(hardware.compare_traces(rows, rows, 123), {"cycle": 5, "word": 123})
        changed = [dict(r) for r in rows]
        changed[5]["in2_st0"] = 124
        with self.assertRaisesRegex(ValueError, "payload"):
            hardware.compare_traces(rows, changed, 123)
        with self.assertRaisesRegex(ValueError, "expected"):
            hardware.compare_traces(changed, changed, 123)
        with self.assertRaisesRegex(ValueError, "completion"):
            hardware.compare_traces(rows[:5], rows[:5], 123)

    def test_runtime_hardware_controls(self):
        """Runs actual imported Lean hardware on negative/overflow inputs and the Task 2 vector."""
        path = ROOT / "Task2/HardwareControls.lean"
        self.assertTrue(path.exists(), "imported hardware numerical runner is missing")
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["LEAN_PATH"] = str(ROOT / ".lake/build/lib/lean")
            target = Path(td) / "traces.json"
            done = subprocess.run(["lean", "--run", str(path), str(ROOT / "build/reference/word-controls.json"), str(target)],
                                  cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            self.assertEqual(done.returncode, 0, done.stdout)
            controls = json.loads(target.read_text())
            self.assertEqual([c["result"] for c in controls], [0, 0xfffffffa, 0x80000000, 0xfffffffe, 0x80000000, 0, 816])
            self.assertTrue(all(c["ram_reset_preserved"] for c in controls))

    def test_scalar_padding_preserves_initial_states(self):
        """Checks original known bits and freedom of the unreachable extra word."""
        hardware = self.hardware()
        self.assertTrue(hasattr(hardware, "pad_scalar_memories"), "word-preserving memory adapter is missing")
        module = {"ports": {}, "netnames": {}, "cells": {"scratch": {
            "type": "$mem_v2", "attributes": {},
            "parameters": {"SIZE": "1", "OFFSET": "0", "ABITS": "1", "WIDTH": "100", "INIT": "10xx",
                           "RD_PORTS": "1", "WR_PORTS": "1"},
            "connections": {"RD_ADDR": ["0"], "WR_ADDR": ["0"]}}}}
        padded, evidence = hardware.pad_scalar_memories(module)
        known = hardware.upstream().state_initial(padded, "scratch", {"kind": "memory", "address_width": 1, "width": 4})["words"]
        valid = lambda words: all((word & init["mask"]) == init["value"] for word, init in zip(words, known))
        self.assertTrue(valid([8, 0]))
        self.assertTrue(valid([11, 15]))
        self.assertFalse(valid([0, 0]))
        self.assertEqual(module["cells"]["scratch"]["parameters"]["INIT"], "10xx")
        self.assertEqual(len(evidence), 1)
        module["cells"]["scratch"]["connections"]["WR_ADDR"] = ["1"]
        with self.assertRaisesRegex(ValueError, "zero address"):
            hardware.pad_scalar_memories(module)

    def test_memory_clock_lifting_checks_source_clock(self):
        """Allows implicit cycle writes only for previously checked positive global-clock ports."""
        hardware = self.hardware()
        self.assertTrue(hasattr(hardware, "lift_memory_clock"), "single-clock RAM adapter is missing")
        module = {"ports": {"clock": {"direction": "input", "bits": [2]}}, "netnames": {}, "cells": {"ram": {
            "type": "$mem_v2", "attributes": {}, "parameters": {"WR_PORTS": "1", "WR_CLK_ENABLE": "1", "WR_CLK_POLARITY": "1"},
            "connections": {"WR_CLK": [2]}}}}
        normalized, evidence = hardware.lift_memory_clock(module)
        self.assertEqual(normalized["cells"]["ram"]["parameters"]["WR_CLK_ENABLE"], "0")
        self.assertEqual(len(evidence), 1)
        module["cells"]["ram"]["connections"]["WR_CLK"] = [9]
        with self.assertRaisesRegex(ValueError, "global clock"):
            hardware.lift_memory_clock(module)


if __name__ == "__main__":
    unittest.main()
