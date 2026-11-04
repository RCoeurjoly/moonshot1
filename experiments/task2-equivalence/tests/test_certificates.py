"""Symbolic candidates are untrusted; Lean must check each transition."""
import importlib.util
from pathlib import Path
import unittest
import os
import subprocess
import tempfile


class CertificateTests(unittest.TestCase):
    def load(self):
        path = Path(__file__).resolve().parents[1] / "scripts/prove_trace.py"
        self.assertTrue(path.exists(), "transition certificate generator is missing")
        spec = importlib.util.spec_from_file_location("prove_trace", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_reassembly_and_masked_unknown(self):
        terms = self.load().Terms()
        x = terms.make("raw", 32, extra="s45")
        pieces = [terms.apply("extract", 1, [x], offset=i) for i in range(32)]
        assembled = pieces[-1]
        for piece in reversed(pieces[:-1]):
            assembled = terms.apply("concat", assembled.width + 1, [assembled, piece])
        self.assertEqual(assembled, x)
        zero = terms.const(0, 32)
        self.assertEqual(terms.apply("bvand", 32, [x, zero]), zero)
        self.assertEqual(terms.apply("bvand", 32, [zero, x]), zero)

    def test_unknown_initial_registers_are_retained(self):
        module = self.load()
        root = Path(__file__).resolve().parents[1]
        import json
        ir = json.loads((root / "build/hardware/baseline/cycle-ir.json").read_text())
        trace = module.SymbolicTrace(ir)
        self.assertEqual(trace.state["s45"].op, "raw")
        self.assertEqual(trace.start.op, "start")
        trace.advance()
        self.assertEqual(trace.cycle, 1)
        self.assertIsNone(trace.observed)

    def test_corrupt_payload_has_counterexample(self):
        """The real imported trajectory must expose a one-bit output mutation."""
        root = Path(__file__).resolve().parents[1]
        source = root / "Task2/MutationControl.lean"
        self.assertTrue(source.exists(), "payload mutation control is missing")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)/"witness.json"
            run = subprocess.run(["lake", "env", "lean", "--run", str(source), str(output)],
                                 cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
            import json
            witness=json.loads(output.read_text())
            self.assertEqual(witness["original"], 816)
            self.assertEqual(witness["mutant"], 817)
            self.assertEqual(witness["edges"], 436)

    def test_kernel_rejects_corrupted_cut_equation(self):
        """A deliberately wrong reset input cannot satisfy the checked cut."""
        root = Path(__file__).resolve().parents[1]
        folder = root / "build/certificates-all"
        source = folder / "BaselineCuts0.lean"
        self.assertTrue(source.exists(), "generate chunk certificates before this control")
        text=source.read_text().split("theorem cut0_1")[0]
        # The right-hand side remains the reset-high normalized circuit output.
        text=text.replace("Task2.Imported.BaselineAdapter.inputs (state0 a b raw seedStart)",
                          "{ (Task2.Imported.BaselineAdapter.inputs (state0 a b raw seedStart)) with i0 := 0#1 }")
        text+="\nend Task2.Imported.BaselineTrace\n"
        with tempfile.TemporaryDirectory(dir=root/"build") as td:
            mutant=Path(td)/"CorruptCut.lean";mutant.write_text(text)
            result=subprocess.run(["lake", "env", "lean", str(mutant)],cwd=root,
                                  capture_output=True,text=True,timeout=60)
            self.assertNotEqual(result.returncode,0,"a false circuit equation was accepted")
            self.assertRegex(result.stdout+result.stderr,r"unsolved goals|`simp` made no progress")
            self.assertNotIn("unexpected token",result.stdout+result.stderr)
            self.assertNotIn("lean.unknownIdentifier",result.stdout+result.stderr)

    def test_direct_submission_still_requires_kernel_validation(self):
        root=Path(__file__).resolve().parents[1]
        source="""import Task2.ProofTools
theorem bad_reflexivity : (1 : Nat) = 2 := by kernel_rfl
theorem bad_submission : (1 : Nat) = 2 := by kernel_exact (Eq.refl (2 : Nat))
"""
        with tempfile.TemporaryDirectory(dir=root/"build") as td:
            path=Path(td)/"FalseKernelControl.lean";path.write_text(source)
            result=subprocess.run(["lake","env","lean",str(path)],cwd=root,
                                  capture_output=True,text=True,timeout=60)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((result.stdout+result.stderr).count("(kernel) declaration type mismatch"),2)


if __name__ == "__main__":
    unittest.main()
