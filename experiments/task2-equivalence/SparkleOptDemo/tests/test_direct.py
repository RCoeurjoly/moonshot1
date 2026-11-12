import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
class DirectMappingTests(unittest.TestCase):
    def module(self):
        path=ROOT/'direct.py'
        self.assertTrue(path.exists(),'direct native relation generator is missing')
        sys.path.insert(0,str(ROOT))
        try:
            spec=importlib.util.spec_from_file_location('opt_direct',path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            return module
        finally:sys.path.pop(0)
    def test_relation_keeps_copies_expands_bits_and_records_removed_state(self):
        module=self.module()
        base={'registers':[{'name':'q','width':8},{'name':'word','width':64},{'name':'removed','width':8}]}
        opt={'registers':[{'name':'q','width':8},{'name':'word_reg_4_','width':1}]}
        relation=module.embedding_map(base,opt,{})
        self.assertEqual([r['kind'] for r in relation],['copy','expand_bit','zero'])
        self.assertEqual(relation[1]['bit'],4)
        opt['registers'].append({'name':'unknown','width':1})
        with self.assertRaisesRegex(ValueError,'unmapped'):
            module.embedding_map(base,opt,{})
