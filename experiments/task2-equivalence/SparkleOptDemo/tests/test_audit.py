import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class DependencyAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(ROOT))
        try:
            spec=importlib.util.spec_from_file_location('opt_audit_prover',ROOT/'prove.py')
            cls.proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.proof)
        finally:sys.path.pop(0)
    def run_lean(self,text):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'AuditTest.lean';path.write_text(text)
            return subprocess.run([str(self.proof.LEAN_BIN/'lean'),str(path)],cwd=ROOT,
                env=self.proof.environment(),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
    def test_pure_math_dependencies_are_accepted(self):
        result=self.run_lean('import DirectAudit\ntheorem native_identity (n : Nat) : n = n := by rfl\naudit_native_dependencies native_identity\n')
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertIn('no retained circuit',result.stdout)
    def test_reference_theorem_dependency_is_rejected(self):
        result=self.run_lean('import DirectAudit\nimport Task2.Baseline\naudit_native_dependencies Task2.baseline_correct\n')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('depends on a retained circuit',result.stdout)
    def test_direct_modules_load_without_reference_circuit_models(self):
        result=self.run_lean('import DirectHelpers\nopen Lean Elab Command\nrun_cmd do\n  let env ← getEnv\n  if env.contains `Task2.Imported.CandidateCore.evaluate || env.contains `Task2.Imported.BaselineCore.evaluate then\n    throwError "direct modules imported a reference circuit"\n')
        self.assertEqual(result.returncode,0,result.stdout)
