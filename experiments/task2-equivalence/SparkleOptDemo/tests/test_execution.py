import importlib.util
from pathlib import Path
import sys
import tempfile
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
class ExecutionTests(unittest.TestCase):
    def test_timeout_is_reported_and_recorded(self):
        spec=importlib.util.spec_from_file_location('opt_execution',ROOT/'prepare.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            records=[];started=time.monotonic()
            with self.assertRaises(Exception) as failure:
                module.execute([sys.executable,'-c','import time; time.sleep(5)'],
                               Path(folder)/'timeout.log',records,timeout=.1)
            self.assertIsInstance(failure.exception,RuntimeError)
            self.assertIn('timed out',str(failure.exception))
            self.assertLess(time.monotonic()-started,2)
            self.assertEqual(records[0]['status'],'timed_out')
