import importlib.util
from pathlib import Path
import unittest
import subprocess
import tempfile


class CandidateImportTests(unittest.TestCase):
    def importer(self):
        path=Path(__file__).resolve().parents[1]/"scripts/import_hardware.py"
        spec=importlib.util.spec_from_file_location("candidate_import",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_candidate_uses_its_own_lean_controls_and_flat_rams(self):
        module=self.importer()
        self.assertTrue(hasattr(module,"control_entrypoint"),"design-specific controls are missing")
        entry=module.control_entrypoint("candidate")
        self.assertIn("CandidateAdapter.harness",entry)
        self.assertNotIn("BaselineAdapter",entry)
        original="dut.handshake_memory0._handshake_memory_5[i] = a_mem[i];"
        self.assertEqual(module.control_testbench(original,"baseline"),original)
        self.assertIn("dut.\\handshake_memory0._handshake_memory_5 [i]",module.control_testbench(original,"candidate"))

    def test_candidate_requires_matching_substantive_variant(self):
        module=self.importer()
        self.assertTrue(hasattr(module,"source_artifact"),"recorded variant gate is missing")
        artifact={"path":"/candidate","sha256":"recorded"}
        manifest={"artifacts":{"candidate":artifact}}
        variant={"status":"prepared","artifacts":{"candidate":dict(artifact)}}
        self.assertEqual(module.source_artifact(manifest,"candidate",variant),artifact)
        variant["status"]="no_change"
        with self.assertRaisesRegex(ValueError,"substantive"):
            module.source_artifact(manifest,"candidate",variant)
        variant["status"]="prepared";variant["artifacts"]["candidate"]["sha256"]="another"
        with self.assertRaisesRegex(ValueError,"identity"):
            module.source_artifact(manifest,"candidate",variant)

    def test_optimized_control_cut_uses_required_bit_laws(self):
        root=Path(__file__).resolve().parents[1]
        path=root/"build/proof/candidate/CandidateCuts2.lean"
        if not path.exists():self.skipTest("candidate proof generation is required")
        text=path.read_text();name="cut8_28"
        part=text.split("theorem "+name+" ")[1].split("theorem ")[0]
        source="""import Task2.Imported.CandidateTrace
import Task2.ProofTools
set_option maxHeartbeats 0
set_option linter.unusedSimpArgs false
namespace Task2.Imported.CandidateTrace
"""+"theorem "+name+" "+part+"\nend Task2.Imported.CandidateTrace\n"
        with tempfile.TemporaryDirectory(dir=root/"build") as td:
            path=Path(td)/"OptimizedControlCut.lean";path.write_text(source)
            result=subprocess.run(["lake","env","lean",str(path)],cwd=root,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertNotIn("sorryAx",result.stdout+result.stderr)
