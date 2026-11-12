import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
class ProvenanceTests(unittest.TestCase):
    def test_changed_recorded_c_trace_is_rejected_before_proof(self):
        sys.path.insert(0,str(ROOT))
        try:
            spec=importlib.util.spec_from_file_location('opt_provenance_prover',ROOT/'prove.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        finally:sys.path.pop(0)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/'build';(out/'native').mkdir(parents=True)
            names=['native/Task2RTL.lean','native/Task2RTL.json','normalized.json','case-0-c.csv']
            for name in names:(out/name).write_text('original')
            controls={'status':'passed_controls','cases':[{}]*7,'inputs':[],
                      'artifacts':[module.identity(out/name) for name in names]}
            (out/'result.json').write_text(json.dumps(controls))
            with patch.object(module,'ROOT',root):
                module.verify_controls()
                (out/'case-0-c.csv').write_text('changed accepted payload')
                with self.assertRaisesRegex(ValueError,'identity changed'):
                    module.verify_controls()
