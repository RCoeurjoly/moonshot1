import copy
import importlib.util
from pathlib import Path
import unittest


class EqyContractTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/"scripts/eqy_compare.py"
        self.assertTrue(path.exists(),"shared symbolic RAM comparison harness is missing")
        spec=importlib.util.spec_from_file_location("eqy_compare",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def fixture(self):
        module={"ports":{"clock":{"direction":"input","bits":[1]}},"netnames":{},"cells":{}}
        for i,j in [(0,5),(1,4)]:
            module["cells"][f"handshake_memory{i}._handshake_memory_{j}"]={
                "type":"$mem_v2","parameters":{k:format(v,"032b") for k,v in
                 {"SIZE":16,"WIDTH":32,"ABITS":4,"OFFSET":0,"WR_PORTS":0,"RD_PORTS":1,"RD_CLK_ENABLE":0}.items()},
                "connections":{"RD_ADDR":[2,3,4,5],"RD_DATA":list(range(10+i*32,42+i*32)),"RD_CLK":["0"],"RD_ARST":["0"],"RD_SRST":["0"]}}
            module["cells"][f"handshake_memory{i}._handshake_memory_{j}"]["parameters"]["INIT"]="x"*512
        return module

    def test_ram_words_are_shared_primary_inputs(self):
        module=self.module();original=self.fixture();lifted,evidence=module.lift_input_memories(original)
        self.assertEqual(len(original["cells"]),2)
        self.assertEqual(set(lifted["ports"]),{"clock","task2_words_a","task2_words_b"})
        self.assertEqual(len(lifted["ports"]["task2_words_a"]["bits"]),512)
        self.assertEqual(len(set(lifted["ports"]["task2_words_a"]["bits"]+lifted["ports"]["task2_words_b"]["bits"])),1024)
        cells=list(lifted["cells"].values())
        self.assertEqual([c["type"] for c in cells],["$shiftx","$shiftx"])
        self.assertEqual(cells[0]["connections"]["B"],["0"]*5+[2,3,4,5])
        self.assertEqual(evidence[0]["port"],"task2_words_a")
        self.assertNotIn("setundef",module.wrapper_text())

    def test_writable_or_fixed_ram_cannot_be_lifted_as_input(self):
        module=self.module()
        for parameter,value in [("WR_PORTS",format(1,"032b")),("INIT","0"*512)]:
            design=self.fixture();next(iter(design["cells"].values()))["parameters"][parameter]=value
            with self.assertRaisesRegex(ValueError,"memory contract"):
                module.lift_input_memories(design)
