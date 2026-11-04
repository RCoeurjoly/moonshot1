"""Exercise reference's first imports in an actually unbuilt Lake project."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

class ReferenceBootstrapTests(unittest.TestCase):
    def test_first_reference_import_builds_missing_upstream_objects(self):
        spec=importlib.util.spec_from_file_location('bootstrap_runner',ROOT/'scripts/run.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        class Emitted(Exception):pass
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'lakefile.lean').write_text('import Lake\nopen Lake DSL\npackage bootstrap_fixture\nlean_lib NN\n')
            (root/'lean-toolchain').write_text('leanprover/lean4:v4.35.0\n')
            for name in ['NN/Runtime/PyTorch/Export/TorchExport.lean','NN/Runtime/IR.lean']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('-- fresh upstream module\n')
            script=root/'scripts/EmitAdapter.lean';script.parent.mkdir()
            script.write_text('import NN.Runtime.PyTorch.Export.TorchExport\nimport NN.Runtime.IR\ndef main : IO Unit := IO.println "BOOTSTRAP_PASS"\n')
            out=root/'build';out.mkdir();(out/'manifest.json').write_text(json.dumps({'artifacts':{}}))
            original=runner.require_run
            def through_first_import(command,log,*args,**kwargs):
                result=original(command,log,*args,**kwargs)
                if 'scripts/EmitAdapter.lean' in command:raise Emitted()
                return result
            with patch.object(runner,'ROOT',root),patch.object(runner,'require_run',side_effect=through_first_import):
                with self.assertRaises(Emitted):
                    runner.reference(argparse.Namespace(out=out,manifest=None))
            self.assertIn('BOOTSTRAP_PASS',(out/'reference/emit.log').read_text())
