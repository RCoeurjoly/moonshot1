"""Use real Lean objects to reject stale source and replaced compiled imports."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

class CacheAttestationTests(unittest.TestCase):
    def test_actual_compiled_closure_is_bound_to_live_sources(self):
        path=ROOT/'scripts/cache_attestation.py'
        self.assertTrue(path.exists(),'cache attestation is missing')
        spec=importlib.util.spec_from_file_location('cache_attestation',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        from run import artifact
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'Task2/Source.lean';source.parent.mkdir()
            source.write_text('namespace Task2\ndef value : Nat := 1\nend Task2\n')
            library=root/'lib';target=library/'Task2/Source.olean';target.parent.mkdir(parents=True)
            env={**os.environ,'LEAN_PATH':str(library)}
            subprocess.run(['lean','-o',str(target),str(source)],env=env,cwd=root,check=True,capture_output=True)
            for name in ['lake-manifest.json','lakefile.lean','lean-toolchain','tool-pins.json','flake.lock']:
                (root/name).write_text('test pin\n')
            checked_object=artifact(target)
            attestation=module.capture(root,root/'build','baseline',{'Task2.Source':artifact(source)},env,
                                       module='Task2.Source',checked_outputs={'Task2.Source':checked_object})
            module.validate(attestation,root,env)
            shadow=root/'shadow/Task2/Source.olean';shadow.parent.mkdir(parents=True)
            alternate=root/'alternate/Source.lean';alternate.parent.mkdir()
            alternate.write_text('namespace Task2\ndef value : Nat := 2\nend Task2\n')
            subprocess.run(['lean','-o',str(shadow),str(alternate)],env=env,cwd=root,check=True,capture_output=True)
            shadow_env={**env,'LEAN_PATH':str(root/'shadow')+':'+str(library)}
            with self.assertRaisesRegex(ValueError,'resolved compiled'):
                module.capture(root,root/'build','baseline',{'Task2.Source':artifact(source)},shadow_env,
                               module='Task2.Source',checked_outputs={'Task2.Source':checked_object})
            import time
            with self.assertRaises(TimeoutError):
                module.validate(attestation,root,env,deadline=time.monotonic()-1)
            source.write_text('namespace Task2\ndef value : Nat := 2\nend Task2\n')
            with self.assertRaisesRegex(ValueError,'source'):
                module.validate(attestation,root,env)
            source.write_text('namespace Task2\ndef value : Nat := 1\nend Task2\n')
            subprocess.run(['lean','-o',str(target),str(alternate)],env=env,cwd=root,check=True,capture_output=True)
            with self.assertRaisesRegex(ValueError,'compiled'):
                module.validate(attestation,root,env)
            with self.assertRaisesRegex(ValueError,'since its successful check'):
                module.capture(root,root/'build','baseline',{'Task2.Source':artifact(source)},env,
                               module='Task2.Source',checked_outputs={'Task2.Source':checked_object})

    def test_missing_attestation_cannot_authorize_replay(self):
        path=ROOT/'scripts/cache_attestation.py'
        self.assertTrue(path.exists(),'cache attestation is missing')
        spec=importlib.util.spec_from_file_location('cache_attestation',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with self.assertRaisesRegex(ValueError,'attestation'):
            module.require({'status':'proved','artifacts':{}})
        import json
        from compare import replay_composition
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            (out/'check-baseline-result.json').write_text(json.dumps({'status':'proved','artifacts':{}}))
            with self.assertRaisesRegex(ValueError,'attestation'):
                replay_composition(out,'baseline',0,1)
