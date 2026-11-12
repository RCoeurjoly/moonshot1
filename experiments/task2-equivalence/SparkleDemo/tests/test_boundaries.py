import copy
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BoundaryTests(unittest.TestCase):
    def runner(self):
        path = ROOT / "run.py"
        self.assertTrue(path.exists(), "Sparkle demo runner is missing")
        spec = importlib.util.spec_from_file_location("sparkle_demo", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_changed_pinned_source_is_rejected(self):
        r = self.runner()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "input.sv"
            p.write_text("original RTL")
            identity = r.file_identity(p)
            r.verify_identity(identity)
            p.write_text("mutated RTL")
            with self.assertRaisesRegex(ValueError, "identity"):
                r.verify_identity(identity)

    def test_failed_rerun_clears_previous_universal_verdict(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            out = Path(td)
            for name in ("result.json", "universal-result.json"):
                (out / name).write_text('{"status":"proved"}')
            env = dict(os.environ, PATH=str(out / "missing-tools"))
            result = subprocess.run([sys.executable, str(ROOT / "run.py"), "--out", str(out)],
                                    env=env, capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((out / "result.json").exists())
            self.assertFalse((out / "universal-result.json").exists())

    def test_compiler_is_selected_from_the_simulation_environment(self):
        r = self.runner()
        with tempfile.TemporaryDirectory() as td:
            compiler = Path(td) / "cc"
            compiler.write_text("#!/bin/sh\nexit 0\n")
            compiler.chmod(0o755)
            self.assertEqual(r.compiler_for({"PATH": td}), str(compiler))

    def memory(self, writes=0):
        return {"type": "$mem_v2", "parameters": {
            "SIZE": f"{16:032b}", "WIDTH": f"{32:032b}",
            "WR_PORTS": f"{writes:032b}", "RD_PORTS": f"{1:032b}"}}

    def test_only_readonly_complete_input_memories_can_be_lifted(self):
        r = self.runner()
        cells = {name: self.memory() for name in r.INPUT_MEMORIES}
        self.assertEqual(len(r.validate_input_memories({"cells": cells})), 2)
        cells[r.INPUT_MEMORIES[0]] = self.memory(writes=1)
        with self.assertRaisesRegex(ValueError, "read.only"):
            r.validate_input_memories({"cells": cells})

    def test_wrong_memory_shape_is_rejected(self):
        r = self.runner()
        cells = {name: self.memory() for name in r.INPUT_MEMORIES}
        cells[r.INPUT_MEMORIES[1]]["parameters"]["SIZE"] = f"{15:032b}"
        with self.assertRaisesRegex(ValueError, "16.*32"):
            r.validate_input_memories({"cells": cells})

    def test_fresh_frontend_exposes_all_input_words(self):
        r = self.runner()
        pins = json.loads((ROOT / "pins.json").read_text())
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            r.prepare_frontend(out, pins, [])
            module = json.loads((out / "normalized.json").read_text())["modules"]["task2"]
            for label in ("a", "b"):
                for k in range(16):
                    port = module["ports"][f"ram_{label}_{k}"]
                    self.assertEqual(port["direction"], "input")
                    self.assertEqual(len(port["bits"]), 32)

    def test_yosys_port_syntax_becomes_ansi_without_changing_body(self):
        r = self.runner()
        source = "module task2(a, y);\n  input [7:0] a;\n  output [7:0] y;\n  assign y = a + 8'h01;\nendmodule\n"
        module = {"ports": {"a": {"direction": "input", "bits": list(range(8))},
                             "y": {"direction": "output", "bits": list(range(8))}}}
        result = r.ansi_header(source, module)
        self.assertIn("input [7:0] a", result)
        self.assertIn("output [7:0] y", result)
        self.assertIn("  assign y = a + 8'h01;\nendmodule\n", result)
        self.assertEqual(result.count("input "), 1)
        self.assertEqual(result.count("output "), 1)

    def trace(self):
        row = dict(cycle=0, reset=0, in3_valid=1, in3_ready=1,
                   out0_valid=0, in2_st0_done_ready=0,
                   in2_st0_valid=0, in2_st0_ready=1, in2_st0=0)
        return [row, dict(row, cycle=1, in3_valid=0,
                          in2_st0_valid=1, in2_st0=816)]

    def test_identical_complete_traces_pass(self):
        r = self.runner()
        self.assertEqual(r.compare_traces(self.trace(), self.trace(), 816),
                         {"edges": 2, "payload": 816})

    def test_handshake_mismatch_is_rejected_even_if_payload_agrees(self):
        r = self.runner()
        wrong = copy.deepcopy(self.trace())
        wrong[0]["in3_ready"] = 0
        with self.assertRaisesRegex(ValueError, "in3_ready"):
            r.compare_traces(self.trace(), wrong, 816)

    def test_mutated_accepted_payload_is_rejected(self):
        r = self.runner()
        wrong = copy.deepcopy(self.trace())
        wrong[1]["in2_st0"] = 817
        with self.assertRaisesRegex(ValueError, "payload"):
            r.compare_traces(self.trace(), wrong, 816)

    def test_truncated_trace_and_missing_completion_are_rejected(self):
        r = self.runner()
        with self.assertRaisesRegex(ValueError, "length"):
            r.compare_traces(self.trace(), self.trace()[:-1], 816)
        missing = self.trace()[:-1]
        with self.assertRaisesRegex(ValueError, "completion"):
            r.compare_traces(missing, missing, 816)

    def test_duplicate_completion_and_nonconsecutive_cycles_are_rejected(self):
        r = self.runner()
        duplicate = self.trace() + [dict(self.trace()[1], cycle=2)]
        with self.assertRaisesRegex(ValueError, "completion"):
            r.compare_traces(duplicate, duplicate, 816)
        wrong = self.trace()
        wrong[1]["cycle"] = 9
        with self.assertRaisesRegex(ValueError, "cycle"):
            r.compare_traces(wrong, wrong, 816)


if __name__ == "__main__":
    unittest.main()
