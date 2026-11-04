import copy
import importlib.util
from pathlib import Path
import unittest


class VariantTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/"scripts/variant.py"
        self.assertTrue(path.exists(),"pipeline variant experiment is missing")
        spec=importlib.util.spec_from_file_location("task2_variant",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def fixture(self):
        return {"ports":{"a":{"direction":"input","bits":[1]*32},
                         "y":{"direction":"output","bits":[2]*32}},
                "cells":{"register":{"type":"$dff","parameters":{"WIDTH":"100000"}},
                         "mux":{"type":"$mux","parameters":{"WIDTH":"100000"}}}}

    def test_noop_or_renaming_is_not_a_pipeline_change(self):
        module=self.module();before=self.fixture();after=copy.deepcopy(before)
        after["cells"]["renamed"]=after["cells"].pop("mux")
        after["attributes"]={"src":"another-file.sv"}
        self.assertEqual(module.structural_delta(before,after)["status"],"no_change")

    def test_removed_logic_is_substantive(self):
        module=self.module();before=self.fixture();after=copy.deepcopy(before)
        del after["cells"]["mux"]
        result=module.structural_delta(before,after)
        self.assertEqual(result["status"],"prepared")
        self.assertEqual(result["before"]["state_bits"],32)
        self.assertEqual(result["after"]["cell_types"],{"$dff":1})

    def test_interface_change_is_rejected(self):
        module=self.module();before=self.fixture();after=copy.deepcopy(before)
        after["ports"]["a"]["bits"]=[1]*16
        with self.assertRaisesRegex(ValueError,"interface"):
            module.structural_delta(before,after)
