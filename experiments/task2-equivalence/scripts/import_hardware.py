#!/usr/bin/env python3
"""Hardware import and concrete trace correspondence controls (not a proof)."""
import copy
import json
import os
from pathlib import Path
import sys
import shutil
import subprocess
import csv

ROOT = Path(__file__).resolve().parents[1]


def integer(value):
    return int(value, 2) if isinstance(value, str) else value


def pad_scalar_memories(module):
    """Keep an always-address-zero scalar RAM word-level for FunctionalIR.

    Native FunctionalIR cannot encode an array whose address sort has zero bits.
    The extra word is unreachable and has no fixed initial bits.
    """
    normalized = copy.deepcopy(module)
    evidence = []
    for name, cell in normalized["cells"].items():
        if cell["type"] != "$mem_v2" or integer(cell["parameters"]["SIZE"]) != 1:
            continue
        p = cell["parameters"]
        if integer(p["OFFSET"]) != 0 or integer(p["ABITS"]) != 1:
            raise ValueError("scalar padding requires a zero-based one-bit address port")
        for direction in ("RD", "WR"):
            addresses = cell["connections"][direction + "_ADDR"]
            if len(addresses) != integer(p[direction + "_PORTS"]) or any(bit != "0" for bit in addresses):
                raise ValueError("scalar padding requires every port to use constant zero address")
        width = integer(p["WIDTH"])
        if width < 1 or len(p["INIT"]) != width:
            raise ValueError("scalar memory initializer has the wrong width")
        evidence.append({"cell": name, "width": width, "source_init": p["INIT"],
                         "source_size": 1, "target_size": 2,
                         "reason": "all read/write addresses are constant zero; extra word stays unreachable and unconstrained"})
        p["SIZE"] = f"{2:032b}"
        p["INIT"] = "x" * width + p["INIT"]
    return normalized, evidence


def lift_memory_clock(module):
    """Translate checked synchronous writes to the implicit cycle clock.

    One FunctionalIR transition is one positive edge, as with formalff -clk2ff.
    This is not permission to import a genuinely asynchronous source write.
    """
    normalized = copy.deepcopy(module)
    clock = module["ports"].get("clock", {}).get("bits", [])
    if len(clock) != 1 or not isinstance(clock[0], int):
        raise ValueError("memory lifting requires one identified global clock")
    evidence = []
    for name, cell in normalized["cells"].items():
        if cell["type"] != "$mem_v2":
            continue
        p = cell["parameters"]
        count = integer(p["WR_PORTS"])
        if not count:
            continue
        if p["WR_CLK_ENABLE"] != "1" * count or p["WR_CLK_POLARITY"] != "1" * count or cell["connections"]["WR_CLK"] != clock * count:
            raise ValueError("memory writes must use the same positive global clock")
        evidence.append({"cell": name, "ports": count, "source_clock": clock,
                         "source_polarity": p["WR_CLK_POLARITY"], "cycle_semantics": "one positive global edge per Device.step"})
        p["WR_CLK_ENABLE"] = "0" * count
        cell["connections"]["WR_CLK"] = ["0"] * count
    return normalized, evidence


def upstream():
    sys.dont_write_bytecode = True
    source = Path(os.environ.get("TASK2_HARDWARE_IMPORTER", ROOT / "build/deps/xiangshan2Lean"))
    sys.path.insert(0, str(source / "scripts"))
    import functional_ir
    return functional_ir


def preflight(module):
    """Adapt only the zero-port bitmap representation seen in real Yosys JSON.

    Upstream iterates bitmap string length, but Yosys prints '0' for a
    zero-width bitmap. No original cells/metadata or transition rules are changed.
    """
    checker_input = copy.deepcopy(module)
    for cell in checker_input["cells"].values():
        if cell["type"] != "$mem_v2":
            continue
        parameters = cell["parameters"]
        for direction in ("RD", "WR"):
            count = parameters[direction + "_PORTS"]
            count = int(count, 2) if isinstance(count, str) else count
            if count == 0:
                if cell["connections"][direction + "_CLK"]:
                    raise ValueError("zero-port memory has clock connections")
                for suffix in ("_CLK_ENABLE", "_CLK_POLARITY"):
                    key = direction + suffix
                    if parameters[key] not in ("", "0", 0):
                        raise ValueError("unexpected zero-width memory bitmap")
                    parameters[key] = ""
    return upstream().preflight(checker_input, "clock", clock_mode="single")


def payload_event(row):
    """Sample accepted result data at a rising edge outside reset."""
    if not row["rising"] or row["reset"] or not row["in2_st0_valid"] or not row["in2_st0_ready"]:
        return None
    word = row["in2_st0"]
    if type(word) is not int or not 0 <= word < 2**32:
        raise ValueError("accepted payload is not a complete 32-bit word")
    return word


def emit_adapter(ir, canonical, destination, design="baseline"):
    """Emit the fixed positive-edge driver around the actual imported transfer.

    Zero-filled fields below construct one witness. The initial relation leaves
    every other raw register unconstrained, and quantifies over both input RAMs.
    """
    f = upstream()
    from lean_records import access_paths, record_expression
    core = ir["namespace"]
    namespace = core.removesuffix("Core") + "Adapter"
    group = ir.get("lean_record_group_size", 128)
    paths = access_paths((s["field"] for s in ir["states"]), group)
    memories = []
    for name in ("handshake_memory0._handshake_memory_5", "handshake_memory1._handshake_memory_4"):
        fields = [s for s in ir["states"] if s["name"] == name]
        if len(fields) != 1 or fields[0]["sort"] != {"kind": "memory", "address_width": 4, "width": 32}:
            raise ValueError(f"unsupported input memory mapping: {name}")
        cell = canonical["cells"][name]
        number = lambda x: int(x, 2) if isinstance(x, str) else x
        p = cell["parameters"]
        if cell["type"] != "$mem_v2" or any(number(p[k]) != v for k, v in {"SIZE": 16, "WIDTH": 32, "WR_PORTS": 0, "RD_PORTS": 1}.items()):
            raise ValueError(f"input RAM provenance/ports differ: {name}")
        if any(word["mask"] for word in fields[0]["initial"]["words"]):
            raise ValueError("input memory has fixed initial bits; cannot represent every input word")
        memories.append(fields[0])
    output = {s["name"]: s for s in ir["outputs"]}
    for name, width in {"in3_ready": 1, "in2_st0_valid": 1, "in2_st0": 32}.items():
        if output[name]["sort"] != {"kind": "bits", "width": width}:
            raise ValueError("payload/handshake output has unexpected width")
    known = {"reset", "clock", "in3_valid", "in2_st0_done_valid", "out0_ready", "in2_st0_ready"}
    if {s["name"] for s in ir["inputs"]} != known:
        raise ValueError("unsupported hardware inputs or arbitrary-value ports")
    values = {"reset": "if s.cycles < 4 then 1 else 0", "clock": "1", "in3_valid": "if s.start then 1 else 0",
              "in2_st0_done_valid": "0", "out0_ready": "1", "in2_st0_ready": "1"}
    inputs = record_expression([(s["field"], "(" + values[s["name"]] + ")") for s in ir["inputs"]], group)
    witness_fields = []
    for s in ir["states"]:
        if s in memories:
            value = "(fun address => " + ("a" if s == memories[0] else "b") + " ⟨address.toNat, address.isLt⟩)"
        elif s["sort"]["kind"] == "bits":
            value = f'({s["initial"]["value"]}#{s["sort"]["width"]})'
        elif s["sort"]["kind"] == "memory":
            width = s["sort"]["width"]
            values = [word["value"] for word in s["initial"]["words"]]
            if len(set(values)) == 1:
                value = f'(fun _ => ({values[0]}#{width}))'
            else:
                literals = ", ".join(f"({word}#{width})" for word in values)
                value = f'(fun address => (#[{literals}])[address.toNat]!)'
        else:
            raise ValueError("unmapped memory state")
        witness_fields.append((s["field"], value))
    a_path, b_path = [paths[s["field"]] for s in memories]
    ready, valid, data = [output[n]["field"] for n in ("in3_ready", "in2_st0_valid", "in2_st0")]
    rows = [f"import {core}", "import Task2.Trace", "set_option maxRecDepth 65536", "set_option maxHeartbeats 0",
            f"namespace {namespace}", "open Task2", "structure State where", f"  raw : {core}.State",
            "  cycles : Nat", "  start : Bool", "  observed : Option Word", "",
            f"def inputs (s : State) : {core}.Inputs := {inputs}", "",
            "def step (s : State) : State :=", f"  let r := {core}.evaluate (inputs s) s.raw",
            "  { raw := r.nextState, cycles := s.cycles + 1,",
            f"    start := if s.cycles < 4 then true else if r.outputs.{ready} != 0 then false else s.start,",
            f"    observed := if s.cycles < 4 then none else if r.outputs.{valid} == 1 then some r.outputs.{data} else none }}", "",
            "def initial (a b : Words) (s : State) : Prop :=", "  s.cycles = 0 ∧ s.observed = none ∧",
            f"  {core}.initialValid s.raw = true ∧",
            f"  s.raw.{a_path} = (fun address => a ⟨address.toNat, address.isLt⟩) ∧",
            f"  s.raw.{b_path} = (fun address => b ⟨address.toNat, address.isLt⟩)", "",
            "def witness (a b : Words) : State :=", "  { raw := " + record_expression(witness_fields, group) + ",",
            "    cycles := 0, start := false, observed := none }", "",
            "theorem initial_exists (a b : Words) : ∃ s, initial a b s := by",
            "  exact ⟨witness a b, rfl, rfl, rfl, rfl, rfl⟩", "",
            "def advance (s : State) : Nat → State", "  | 0 => s", "  | n + 1 => step (advance s n)", ""]
    for label, path in [("A", a_path), ("B", b_path)]:
        rows += [f"theorem memory{label}_step (s : State) : (step s).raw.{path} = s.raw.{path} := by rfl", "",
                 f"theorem memory{label}_preserved (s : State) (n : Nat) :",
                 f"    (advance s n).raw.{path} = s.raw.{path} := by", "  induction n with", "  | zero => rfl",
                 f"  | succ n ih => exact Eq.trans (memory{label}_step (advance s n)) ih", ""]
    rows += ["def harness : Task2.Trace.Harness where", "  State := State", "  seed := witness", "  step := step",
             f"  memoryA := fun s => s.raw.{a_path}", f"  memoryB := fun s => s.raw.{b_path}", "  sample := fun s =>",
             f"    let r := {core}.evaluate (inputs s) s.raw", "    { cycle := s.cycles, reset := decide (s.cycles < 4), start := s.start,",
             f"      startReady := r.outputs.{ready} == 1, tokenValid := r.outputs.{output['out0_valid']['field']} == 1,",
             f"      doneReady := r.outputs.{output['in2_st0_done_ready']['field']} == 1, payloadReady := true,",
             f"      payloadValid := r.outputs.{valid} == 1, data := r.outputs.{data} }}", ""]
    rows += [f"end {namespace}", "namespace Task2.Imported", f"def {design} : Task2.Device where",
             f"  State := {namespace}.State", f"  initial := {namespace}.initial", f"  step := {namespace}.step",
             "  result := (·.observed)", "end Task2.Imported"]
    rows += [f"#print axioms {namespace}.{theorem}" for theorem in ("initial_exists", "memoryA_preserved", "memoryB_preserved")]
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(rows) + "\n")


def compare_traces(lean_rows, rtl_rows, expected):
    if len(lean_rows) != len(rtl_rows):
        raise ValueError("trace cycle count differs")
    event = None
    ports = ("cycle", "reset", "in3_valid", "in3_ready", "out0_valid", "in2_st0_done_ready", "in2_st0_valid", "in2_st0_ready")
    for index, (lean, rtl) in enumerate(zip(lean_rows, rtl_rows)):
        if lean["cycle"] != index or lean["reset"] != int(index < 4):
            raise ValueError("trace does not follow the four-edge reset contract")
        if any(lean[k] != rtl[k] for k in ports):
            raise ValueError(f"handshake trace differs at cycle {index}")
        left, right = payload_event(lean), payload_event(rtl)
        if left != right:
            raise ValueError(f"accepted payload differs at cycle {index}: {left} / {right}")
        if left is not None and event is None:
            if left != expected:
                raise ValueError(f"payload {left} differs from expected {expected}")
            event = {"cycle": index, "word": left}
    if event is None:
        raise ValueError("no completion event in the retained trace")
    return event


def source_artifact(manifest, design, variant=None):
    if design=="baseline":return manifest["artifacts"]["baseline"]
    if design!="candidate":raise NotImplementedError("unknown hardware design")
    if variant is None or variant["status"]!="prepared":
        raise ValueError("candidate requires a recorded substantive pipeline variant")
    artifact=manifest["artifacts"]["candidate"]
    if artifact["sha256"]!=variant["artifacts"]["candidate"]["sha256"]:
        raise ValueError("candidate variant artifact identity differs")
    return artifact


def control_entrypoint(design):
    name=design.title()
    return f"import Task2.Imported.{name}Adapter\n\ndef main (args : List String) : IO Unit :=\n  Task2.Trace.runControls Task2.Imported.{name}Adapter.harness args\n"


def control_testbench(text, design):
    if design=="candidate":
        for number,memory in [(0,5),(1,4)]:
            path=f"handshake_memory{number}._handshake_memory_{memory}"
            text=text.replace("dut."+path+"[", "dut.\\"+path+" [")
    return text


def import_design(manifest, out, design, yosys="yosys"):
    from run import artifact, require_run, write_json, audit_axioms, find_derivation, verify_manifest
    out = Path(out).resolve()
    work = out / "hardware" / design
    work.mkdir(parents=True, exist_ok=True)
    variant=json.loads((out/"variant-result.json").read_text()) if design=="candidate" else None
    if variant is not None:verify_manifest(variant)
    sources = Path(source_artifact(manifest,design,variant)["path"]) / "sources.f"
    frontend = work / "frontend.ys"
    cleanup=["opt_expr","opt_muxtree","opt_clean"] if design=="candidate" else []
    frontend.write_text("\n".join([
        f"read_slang --top main --no-proc --no-synthesis-define --no-default-translate-off-format -f {sources}",
        "hierarchy -check -top main", "proc -noopt", "flatten", "opt_clean", "memory_collect",
        "memory_map t:$mem_v2 r:SIZE=1 %i", "select *", "opt_clean"]+cleanup+["check -assert",
        f"write_rtlil {work / 'canonical.il'}", f"write_json {work / 'canonical.json'}", ""]) )
    runs = [require_run([yosys, "-Q", "-T", "-m", "slang", "-s", str(frontend)], work / "frontend.log")]
    canonical = json.loads((work / "canonical.json").read_text())["modules"]["main"]
    clock_check = preflight(canonical)
    write_json(work / "preflight.json", clock_check)
    normalize = work / "normalize.ys"
    normalize.write_text("\n".join([
        f"read_rtlil {work / 'canonical.il'}", "formalff -clk2ff", "memory_nordff", "opt_clean",
        "setundef -undriven -anyseq", "check -assert", f"write_json {work / 'cycle.json'}",
        *([f"write_functional_smt2 {work / 'cycle.smt2'}"] if design=="baseline" else []), ""]))
    runs.append(require_run([yosys, "-Q", "-T", "-s", str(normalize)], work / "normalize.log"))
    module = json.loads((work / "cycle.json").read_text())["modules"]["main"]
    if any(c["type"] == "$anyseq" for c in module["cells"].values()):
        raise NotImplementedError("additional arbitrary input ports need an explicit environment contract")
    if design=="candidate":
        export=work/"export-functional.ys"
        export.write_text(f"read_json {work/'cycle.json'}\nwrite_functional_smt2 {work/'cycle.smt2'}\n")
        runs.append(require_run([yosys,"-Q","-T","-s",str(export)],work/"export-functional.log"))
    f = upstream()
    core_namespace = "Task2.Imported." + design.title() + "Core"
    # The native SMT initializer assertions are intentionally ignored by this
    # pinned parser; real known/unknown initial bits come from matching JSON.
    ir = f.import_functional((work / "cycle.smt2").read_text(), f.import_metadata(module), core_namespace, None)
    ir.update(clock_mode="single-positive-edge", arbitrary_inputs=[])
    write_json(work / "cycle-ir.json", ir)
    generated = out / "generated/Task2/Imported"
    generated.mkdir(parents=True, exist_ok=True)
    core = generated / (design.title() + "Core.lean")
    core.write_text(f.emit_lean(ir,chunk_size=128))
    adapter = generated / (design.title() + "Adapter.lean")
    emit_adapter(ir, canonical, adapter, design)
    objects = ROOT / ".lake/build/lib/lean/Task2/Imported"
    objects.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["LEAN_PATH"] = str(ROOT / ".lake/build/lib/lean")
    runs.append(require_run(["lean", "-o", str(objects.parent / "Trace.olean"), "Task2/Trace.lean"],
                            work / "Trace.log", env=env))
    for source in (core, adapter):
        runs.append(require_run(["lean", "--root=" + str(out / "generated"), "-o", str(objects / (source.stem + ".olean")), str(source)],
                                work / (source.stem + ".log"), env=env))
    proof_output = (work / (adapter.stem + ".log")).read_text()
    assumptions = {name: audit_axioms(proof_output, core_namespace.removesuffix("Core") + "Adapter." + name)
                   for name in ("initial_exists", "memoryA_preserved", "memoryB_preserved")}
    controls = work / "controls"
    controls.mkdir(exist_ok=True)
    lean_trace = controls / "lean-traces.json"
    requests = out / "reference/word-controls.json"
    control_source=controls/"Controls.lean"
    control_source.write_text(control_entrypoint(design))
    runs.append(require_run(["lean", "--run", str(control_source), str(requests), str(lean_trace)],
                            controls / "lean.log", env=env))
    lean_cases = json.loads(lean_trace.read_text())
    graph = json.loads(Path(manifest["artifacts"]["derivation_graph"]["path"]).read_text())
    _, simulation = find_derivation(graph, "sim-main")
    build_inputs = simulation["env"]["buildInputs"].split()
    verilator = next(Path(p) / "bin/verilator" for p in build_inputs if "verilator" in Path(p).name)
    simulation_env = dict(os.environ)
    simulation_env["PATH"] = ":".join(str(Path(p) / "bin") for p in build_inputs) + ":" + simulation_env["PATH"]
    testbench=controls/"control_tb.sv"
    testbench.write_text(control_testbench((ROOT/"scripts/control_tb.sv").read_text(),design))
    obj = controls / "obj_dir"
    runs.append(require_run([str(verilator), "--binary", "--timing", "--language", "1800-2017", "-Wno-fatal",
                             "-top", "tb_control", "-Mdir", str(obj), "-o", "sim_control", "-f", str(sources),
                             str(testbench)], controls / "verilator-build.log", env=simulation_env))
    cases = json.loads(requests.read_text())
    cases.append({"input_words": [list(range(1, 17)), list(range(16, 0, -1))], "expected_output_words": [[816]]})
    comparison = []
    if len(lean_cases) != len(cases):
        raise ValueError("Lean/RTL control case count differs")
    for index, case in enumerate(cases):
        a_path, b_path = [controls / f"case-{index}-{name}.hex" for name in ("a", "b")]
        for path, words in zip((a_path, b_path), case["input_words"]):
            path.write_text("".join(f"{word:08x}\n" for word in words))
        expected = case["expected_output_words"][0][0]
        rtl_trace = controls / f"case-{index}-rtl.csv"
        runs.append(require_run([str(obj / "sim_control"), f"+A={a_path}", f"+B={b_path}",
                                 f"+EXPECTED={expected:08x}", f"+TRACE={rtl_trace}"], controls / f"case-{index}-rtl.log"))
        with rtl_trace.open() as stream:
            rows = [{**{k: int(v) for k, v in row.items()}, "rising": True} for row in csv.DictReader(stream)]
        event = compare_traces(lean_cases[index]["trace"], rows, expected)
        comparison.append({"case": index, **event, "edges": event["cycle"] + 1, "rtl_trace": artifact(rtl_trace)})
    write_json(controls / "comparison.json", comparison)
    bound = {"baseline": manifest["artifacts"]["baseline"]}
    if design=="candidate":bound["candidate"]=manifest["artifacts"]["candidate"]
    if design=="candidate":bound["functional_export_script"]=artifact(export)
    for name, path in [("frontend_script", frontend), ("normalization_script", normalize), ("canonical", work / "canonical.il"),
                       ("native_smt", work / "cycle.smt2"), ("initialization_metadata", work / "cycle.json"),
                       ("functional_ir", work / "cycle-ir.json"), ("imported_core", core), ("device_adapter", adapter),
                       ("trace_semantics", ROOT / "Task2/Trace.lean"), ("testbench", testbench), ("control_entrypoint",control_source),
                       ("lean_trace", lean_trace), ("trace_comparison", controls / "comparison.json"), ("word_controls", requests),
                       ("importer", Path(f.__file__)), ("experiment_importer", Path(__file__)), ("tool_pins", ROOT / "tool-pins.json"),
                       ("flake_lock", ROOT / "flake.lock")]:
        bound[name] = artifact(path)
    return {"status": "passed_control", "design": design, "claim": "imported transition, initialized-state existence, input-RAM preservation and concrete RTL/Lean correspondence",
            "scope": "concrete controls plus universal initialization/RAM lemmas; no universal result-equivalence or completion proof yet",
            "clock_check": clock_check, "nodes": len(ir["nodes"]), "state_fields": len(ir["states"]),
            "axioms": assumptions, "runs": runs, "artifacts": bound,
            "yosys_version": subprocess.check_output([yosys, "-V"], text=True).strip(),
            "initialization": ir["initialization"], "trace_controls": comparison}
