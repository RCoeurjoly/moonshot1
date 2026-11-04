import importlib.util
from pathlib import Path
import unittest


class CompareTests(unittest.TestCase):
    def test_legacy_cache_samples_are_attempts_without_proved_medians(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
        from compare import qualify_replay_evidence
        old={'lean':{'baseline':{'runs':[{'status':'proved','elapsed_seconds':5,'peak_rss_kib':10,'artifacts':{}}]}}}
        corrected=qualify_replay_evidence(old)
        self.assertEqual(old['lean']['baseline']['runs'][0]['status'],'proved','historical input was modified')
        self.assertFalse(corrected['lean']['baseline']['all_proved'])
        self.assertIsNone(corrected['lean']['baseline']['median_proved_wall_seconds'])
        self.assertEqual(corrected['lean']['baseline']['median_attempt_wall_seconds'],5)
        self.assertEqual(corrected['lean']['baseline']['runs'][0]['status'],'inconclusive')

    def test_timeout_cannot_receive_a_proved_replay_median(self):
        path=Path(__file__).resolve().parents[1]/"scripts/compare.py"
        self.assertTrue(path.exists(),"warm comparison runner is missing")
        spec=importlib.util.spec_from_file_location("task2_compare",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        identity={"path":"/checked/source","sha256":"identity"}
        runs=[{"status":"proved","elapsed_seconds":1,"peak_rss_kib":10,"artifacts":{"source":identity}},
              {"status":"timeout","elapsed_seconds":600,"peak_rss_kib":20,"artifacts":{"source":identity}}]
        result=module.summarize_runs(runs)
        self.assertIsNone(result["median_proved_wall_seconds"])
        self.assertEqual(result["median_attempt_wall_seconds"],300.5)
        self.assertEqual(result["runs"][0]["artifacts"]["source"],identity)
        self.assertEqual(result["peak_process_rss_kib"],20)
