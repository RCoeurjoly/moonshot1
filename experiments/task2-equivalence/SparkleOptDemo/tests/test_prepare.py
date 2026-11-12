import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PreparationTests(unittest.TestCase):
    def module(self):
        path = ROOT / 'prepare.py'
        self.assertTrue(path.exists(), 'optimized preparation module is missing')
        spec = importlib.util.spec_from_file_location('opt_prepare', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_pinned_candidate_and_checkpoint_are_verified(self):
        module = self.module()
        pins = json.loads((ROOT/'pins.json').read_text())
        module.verify_pins(pins)

    def test_changed_candidate_is_rejected(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'candidate.sv'
            path.write_text('original')
            pins = {'inputs': {'candidate': module.identity(path)}}
            path.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'identity'):
                module.verify_pins(pins)

    def test_candidate_schema_is_complete_and_bijective(self):
        module = self.module()
        reference = {'inputs': [], 'outputs': [], 'states': [
            {'name':'ram_a', 'sort':{'kind':'memory','width':32,'address_width':4}},
            {'name':'$driver$q', 'sort':{'kind':'bits','width':8}},
            {'name':'ram_b', 'sort':{'kind':'memory','width':32,'address_width':4}}]}
        native = {'registers':[{'name':'q','width':8}]}
        binding = module.reference_schema(reference, native)
        self.assertEqual(binding['state_count'], 3)
        self.assertEqual(binding['memory_indices'], [0,2])
        self.assertEqual(binding['states'], [{'index':1,'wire':'q','width':8}])
        native['registers'].append({'name':'unmapped','width':1})
        with self.assertRaisesRegex(ValueError, 'bijective'):
            module.reference_schema(reference, native)

    def test_mismatched_register_width_is_rejected(self):
        module = self.module()
        reference = {'inputs': [], 'outputs': [], 'states': [
            {'name':'$driver$q','sort':{'kind':'bits','width':8}}]}
        with self.assertRaisesRegex(ValueError,'width'):
            module.reference_schema(reference, {'registers':[{'name':'q','width':7}]})

if __name__ == '__main__': unittest.main()

class ReductionTests(unittest.TestCase):
    def test_yosys_reduction_lowering_removes_implicit_width_comparisons(self):
        path=ROOT/'prepare.py'
        spec=importlib.util.spec_from_file_location('opt_prepare_reductions',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertTrue(hasattr(module,'lower_reductions'),'reduction lowering is missing')
        pins=json.loads((ROOT/'pins.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            sv=out/'source.sv'
            sv.write_text('module task2(input [1:0] a, input [1:0] b, output y); assign y = a || b; endmodule\n')
            import subprocess
            subprocess.run([pins['yosys'],'-Q','-T','-p',
                f'read_verilog {sv}; write_json {out/"normalized.json"}'],check=True,stdout=subprocess.DEVNULL)
            module.lower_reductions(out,pins,[])
            cells=json.loads((out/'normalized.json').read_text())['modules']['task2']['cells']
            self.assertTrue(all(c['type'] not in ['$reduce_bool','$reduce_or','$logic_or'] for c in cells.values()))

class AliasTests(unittest.TestCase):
    def test_register_alias_uses_identical_yosys_bits(self):
        path=ROOT/'prepare.py';spec=importlib.util.spec_from_file_location('opt_prepare_alias',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        reference={'inputs':[],'outputs':[],'states':[{'name':'$driver$word','sort':{'kind':'bits','width':2}}]}
        native={'registers':[{'name':'read_data','width':2}]}
        netnames={'word':{'bits':[8,9]},'read_data':{'bits':[8,9]}}
        self.assertIn('netnames', __import__('inspect').signature(module.reference_schema).parameters,
                      'normalized net aliases are not supported')
        self.assertEqual(module.reference_schema(reference,native,netnames)['states'][0]['wire'],'read_data')
        netnames['read_data']['bits']=[8,10]
        with self.assertRaisesRegex(ValueError,'correspondence'):
            module.reference_schema(reference,native,netnames)

class PartialWireTests(unittest.TestCase):
    def test_partial_internal_writes_are_split_at_driver_boundaries(self):
        import re,subprocess
        path=ROOT/'prepare.py';spec=importlib.util.spec_from_file_location('opt_prepare_partial',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        pins=json.loads((ROOT/'pins.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);sv=out/'source.sv'
            sv.write_text("module task2(input a, input b, input c, output [63:0] y); wire [63:0] mid; assign mid[4]=a?b:c; assign mid[3:0]=4'b0; assign mid[63:5]=59'b0; assign y=mid+64'd1; endmodule\n")
            subprocess.run([pins['yosys'],'-Q','-T','-p',f'read_verilog {sv}; write_json {out/"normalized.json"}'],check=True,stdout=subprocess.DEVNULL)
            module.lower_reductions(out,pins,[])
            self.assertIsNone(re.search(r'assign\s+[^\s=]+\[', (out/'task2.sv').read_text()))
