import importlib.util
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ProcessTimeoutTests(unittest.TestCase):
    def test_timeout_terminates_detached_solver_descendant(self):
        spec=importlib.util.spec_from_file_location("timeout_runner",ROOT/"scripts/run.py")
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);pid_file=root/"solver.pid"
            parent="""import pathlib,subprocess,sys,time
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
pathlib.Path(sys.argv[1]).write_text(str(p.pid))
time.sleep(30)
"""
            result=runner.execute([sys.executable,"-c",parent,str(pid_file)],root/"run.log",timeout=0.5)
            self.assertEqual(result["status"],"timeout")
            self.assertTrue(pid_file.exists(),"child setup did not finish before the timeout")
            pid=int(pid_file.read_text())
            try:
                stat=Path(f"/proc/{pid}/stat")
                state=stat.read_text().rsplit(")",1)[1].split()[0] if stat.exists() else None
                self.assertIn(state,(None,"Z"),"detached solver survived its verification timeout")
            finally:
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
