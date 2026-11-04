import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class EvidenceArchiveTests(unittest.TestCase):
    def archive(self):
        path=ROOT/"scripts/archive_evidence.py"
        self.assertTrue(path.exists(),"proof evidence archiver is missing")
        sys.path.insert(0,str(ROOT/"scripts"))
        spec=importlib.util.spec_from_file_location("archive_evidence",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_sealed_evidence_survives_later_source_edits(self):
        archive=self.archive()
        from run import artifact,verify_manifest
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/"input.lean";source.write_text("checked bytes\n")
            result={"status":"proved","artifacts":{"proof":artifact(source)},
                    "runs":[{"source":artifact(source),"log":artifact(source)}]}
            sealed=archive.seal(result,root/"archive")
            source.write_text("a later experiment\n")
            verify_manifest(sealed)
            self.assertEqual(Path(sealed["artifacts"]["proof"]["path"]).read_text(),"checked bytes\n")
            self.assertEqual(sealed["artifacts"]["proof"]["original_path"],str(source))
            self.assertEqual(sealed["status"],result["status"])
            self.assertEqual(sealed["runs"][0]["log"]["path"],sealed["artifacts"]["proof"]["path"])

    def test_stale_evidence_is_rejected_before_archiving(self):
        archive=self.archive()
        from run import artifact
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/"input.lean";source.write_text("old")
            result={"status":"proved","artifacts":{"proof":artifact(source)}}
            source.write_text("changed before sealing")
            with self.assertRaisesRegex(ValueError,"identity"):
                archive.seal(result,root/"archive")

    def test_archival_proof_does_not_authorize_changed_live_semantics(self):
        archive=self.archive()
        from run import artifact,verify_manifest
        import run
        self.assertTrue(hasattr(run,"require_current_artifact"),"live semantic identity gate is missing")
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/"Source.lean";source.write_text("original semantics")
            result=archive.seal({"artifacts":{"source":artifact(source)}},root/"archive")
            source.write_text("changed live semantics")
            verify_manifest(result)
            with self.assertRaisesRegex(ValueError,"identity"):
                run.require_current_artifact(result,"source",source)
