"""Exercise the native semantics and the fresh-artifact loader boundaries."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = """set_option maxRecDepth 65536
set_option maxHeartbeats 0
set_option linter.unusedVariables false
"""
MODEL = """structure Inputs where
  value : BitVec 8
structure State where
  q : BitVec 8
structure Outputs where
  value : BitVec 8
structure Evaluation where
  outputs : Outputs
  nextState : State
@[noinline] def wire0 (inputs : Inputs) : BitVec 8 := inputs.value + 1
"""


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("sparkle_prove", ROOT / "prove.py")
        cls.proof = importlib.util.module_from_spec(spec)
        # prove.py shares source-identity helpers with run.py.
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            spec.loader.exec_module(cls.proof)
        finally:
            sys.path.pop(0)
        cls.temp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temp.name)
        cls.env = cls.proof.environment()
        cls.env["LEAN_PATH"] = str(cls.work) + ":" + cls.env["LEAN_PATH"]
        result = cls.lean(ROOT / "Proof/NativeArtifact.lean", "-o", cls.work / "NativeArtifact.olean")
        if result.returncode:
            raise RuntimeError(result.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def lean(cls, path, *args):
        return subprocess.run([str(cls.proof.LEAN_BIN / "lean"), str(path), *map(str, args)],
                              cwd=ROOT, env=cls.env, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=60)

    def source(self, body=MODEL):
        return "import Std\nnamespace Task2RTL\n" + OPTIONS + body + "end Task2RTL\n"

    def load(self, source):
        artifact = self.work / "Native.lean"
        artifact.write_text(source)
        driver = self.work / "Check.lean"
        driver.write_text("import NativeArtifact\nopen SparkleProof\n"
                          f"import_native_sparkle {json.dumps(str(artifact))} as Circuit\n")
        return self.lean(driver)

    def test_plain_native_model_loads(self):
        result = self.load(self.source())
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_wrong_header_namespace_and_options_are_rejected(self):
        source = self.source()
        for wrong in (source.replace("import Std", "import Lean"),
                      source.replace("import Std", "import Std\nimport Lean"),
                      "prelude\n" + source,
                      source.replace("Task2RTL", "WrongCircuit"),
                      source.replace("maxHeartbeats 0", "maxHeartbeats 1")):
            with self.subTest(source=wrong[:100]):
                self.assertNotEqual(self.load(wrong).returncode, 0)

    def test_commands_and_declaration_modifiers_are_rejected(self):
        for declaration in ("axiom shortcut : False\n", "#eval IO.println 123\n",
                            "unsafe def shortcut := 1\n", "opaque shortcut : Nat := 1\n",
                            "def _root_.shortcut := 1\n", "@[simp] def shortcut := 1\n"):
            with self.subTest(declaration=declaration):
                result = self.load(self.source(MODEL + declaration))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("native", result.stdout)

    def test_deriving_and_termination_annotations_are_rejected(self):
        for source in (self.source().replace("  q : BitVec 8", "  q : BitVec 8\n  deriving Repr"),
                       self.source(MODEL + "def next0 : Nat := 0\ntermination_by 0\n")):
            with self.subTest(source=source):
                self.assertNotEqual(self.load(source).returncode, 0)

    def test_changed_native_function_does_not_inherit_equality(self):
        original, changed = self.work / "Original.lean", self.work / "Changed.lean"
        original.write_text(self.source())
        changed.write_text(self.source(MODEL.replace("value + 1", "value + 2")))
        driver = self.work / "Mutation.lean"
        driver.write_text("import NativeArtifact\nopen SparkleProof\n"
                          f"import_native_sparkle {json.dumps(str(original))} as Original\n"
                          f"import_native_sparkle {json.dumps(str(changed))} as Changed\n"
                          "theorem artifact_checked (value : BitVec 8) :\n"
                          "  Original.wire0 {value} = Changed.wire0 {value} := by rfl\n")
        result = self.lean(driver)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rfl", result.stdout)

    def test_native_metadata_mutation_is_rejected_before_proof(self):
        native = self.work / "build/native"
        native.mkdir(parents=True, exist_ok=True)
        model, metadata = native / "Task2RTL.lean", native / "Task2RTL.json"
        model.write_text(self.source())
        metadata.write_text('{"registers": []}')
        controls = {"artifacts": [self.proof.file_identity(p) for p in (model, metadata)]}
        with patch.object(self.proof, "ROOT", self.work):
            self.proof.verify_native_artifacts(controls)
            metadata.write_text('{"registers": ["changed"]}')
            with self.assertRaisesRegex(ValueError, "identity changed"):
                self.proof.verify_native_artifacts(controls)

    def test_tactic_and_sorry_bodies_are_rejected_before_elaboration(self):
        marker = self.work / "executed.txt"
        for body in ("by sorry", "sorryAx (BitVec 8) true", "by\n  run_tac do\n"
                     f"    IO.FS.writeFile {json.dumps(str(marker))} \"executed\"\n  exact 0"):
            with self.subTest(body=body):
                result = self.load(self.source(MODEL.replace("inputs.value + 1", body)))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists(), "loader executed an unsupported tactic body")

    def test_native_semantics_and_grouped_state_execute(self):
        result = subprocess.run([str(ROOT / ".lake/build/bin/native-smoke")],
                                cwd=ROOT, text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("grouped register storage", result.stdout)


if __name__ == "__main__":
    unittest.main()
