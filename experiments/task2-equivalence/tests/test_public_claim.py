import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class PublicClaimTests(unittest.TestCase):
    def test_public_theorem_cannot_be_weakened_to_true(self):
        path=ROOT/"scripts/public_claim.py"
        self.assertTrue(path.exists(),"public claim type gate is missing")
        spec=importlib.util.spec_from_file_location("public_claim",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        text=module.audit_text("baseline")
        text=text.replace("import Task2.Baseline", "import Task2.Source\nimport Task2.Imported.BaselineAdapter")
        text=text.replace("namespace Task2.PublicAudit",
                          "theorem Task2.weak_claim : True := True.intro\nnamespace Task2.PublicAudit")
        text=text.replace("Task2.baseline_correct","Task2.weak_claim")
        with tempfile.TemporaryDirectory(dir=ROOT/"build") as td:
            source=Path(td)/"WeakenedClaim.lean";source.write_text(text)
            result=subprocess.run(["lake","env","lean",str(source)],cwd=ROOT,
                                  capture_output=True,text=True,timeout=60)
            self.assertNotEqual(result.returncode,0)
            self.assertRegex(result.stdout+result.stderr,"[Tt]ype mismatch")
            self.assertNotIn("lean.unknownIdentifier",result.stdout+result.stderr)
