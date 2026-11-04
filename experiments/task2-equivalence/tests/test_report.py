import importlib.util
from pathlib import Path
import unittest


class ReportTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/"scripts/report.py"
        self.assertTrue(path.exists(),"measured milestone report is missing")
        spec=importlib.util.spec_from_file_location("task2_report",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def effort(self,baseline,candidate):
        return {"baseline_proof":{"actor":"codex","active_seconds":baseline,"interventions":["construct invariant"],"changed_obligations":["initialization","completion"]},
                "candidate_proof":{"actor":"codex","active_seconds":candidate,"interventions":["reuse"],"changed_obligations":[]},
                "setup":{"active_seconds":100000},"warm_replay":{"baseline":100,"candidate":1}}

    def test_missing_effort_prevents_less_work_claim(self):
        result=self.module().effort_verdict(self.effort(None,None))
        self.assertFalse(result["less_work"])
        self.assertEqual(result["result"],"inconclusive")

    def test_provisioning_and_faster_replay_do_not_count_as_less_proof_work(self):
        result=self.module().effort_verdict(self.effort(100,200))
        self.assertFalse(result["less_work"])
        self.assertEqual(result["result"],"not_less_work")

    def test_instrumented_proof_phase_comparison_is_allowed(self):
        result=self.module().effort_verdict(self.effort(300,30))
        self.assertTrue(result["less_work"])
        self.assertEqual(result["result"],"less_work")
