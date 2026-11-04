"""Untrusted symbolic execution proposing kernel-checked transition certificates.

No result from this module is a proof. The emitted Lean equations must compile
and pass the experiment's axiom audit against the imported hardware definition.
"""
import argparse
import json
import re
import concurrent.futures
import os
import subprocess
import time
from pathlib import Path
from functools import reduce
from operator import and_, or_, mul


class Term:
    def __init__(self, number, op, width, args, extra):
        self.number, self.op, self.width = number, op, width
        self.args, self.extra = args, extra


class Terms:
    def __init__(self):
        self.nodes, self.memo = [], {}

    def make(self, op, width, args=(), extra=None):
        args = tuple(args)
        key = op, width, tuple(a.number for a in args), extra
        if key not in self.memo:
            self.memo[key] = Term(len(self.nodes), op, width, args, extra)
            self.nodes.append(self.memo[key])
        return self.memo[key]

    def const(self, value, width):
        return self.make("constant", width, extra=bool(value) if width is None else value % (1 << width))

    def apply(self, op, width, args, offset=None):
        args = tuple(args)
        if op == "ite":
            if args[0].op == "constant":
                return args[1] if args[0].extra else args[2]
            if args[1] == args[2]:
                return args[1]
        if op == "=" and args[0] == args[1]:
            return self.const(True, None)
        if op in ("bvand", "bvor", "bvadd", "bvmul"):
            zero, ones = self.const(0, width), self.const((1 << width)-1, width)
            if op in ("bvand", "bvmul") and zero in args:
                return zero
            identity = {"bvand": ones, "bvor": zero, "bvadd": zero,
                        "bvmul": self.const(1, width)}[op]
            remaining = tuple(a for a in args if a != identity)
            if not remaining:
                return identity
            if len(remaining) == 1:
                return remaining[0]
            args = remaining
        if op == "zero_extend" and args[0].width == width:
            return args[0]
        if op == "extract":
            x = args[0]
            if offset == 0 and width == x.width:
                return x
            if x.op == "extract":
                return self.apply("extract", width, x.args, offset=offset+x.extra)
            if x.op == "concat":
                low = x.args[1].width
                if offset + width <= low:
                    return self.apply("extract", width, [x.args[1]], offset=offset)
                if offset >= low:
                    return self.apply("extract", width, [x.args[0]], offset=offset-low)
        if op == "concat":
            high, low = args
            if high.op == low.op == "extract" and high.args == low.args and high.extra == low.extra+low.width:
                return self.apply("extract", width, high.args, offset=low.extra)
        if op == "bvshl" and args[1].op == "constant" and args[1].extra == 0:
            return args[0]
        if all(a.op == "constant" for a in args):
            a = [x.extra for x in args]
            if op == "=": value = a[0] == a[1]
            elif op == "extract": value = a[0] >> offset
            elif op == "zero_extend": value = a[0]
            elif op == "concat": value = (a[0] << args[1].width) | a[1]
            elif op == "bvnot": value = ~a[0]
            elif op == "bvand": value = reduce(and_, a)
            elif op == "bvor": value = reduce(or_, a)
            elif op == "bvadd": value = sum(a)
            elif op == "bvmul": value = reduce(mul, a)
            elif op == "bvshl": value = a[0] << min(args[0].width, a[1])
            elif op == "bvsgt":
                w = args[0].width
                signed = lambda x: x if x < 1 << (w-1) else x-(1 << w)
                value = signed(a[0]) > signed(a[1])
            elif op == "ite": value = a[1] if a[0] else a[2]
            else: raise NotImplementedError(op)
            return self.const(value, width)
        return self.make(op, width, args, offset)


class SymbolicTrace:
    def __init__(self, ir):
        self.ir, self.terms = ir, Terms()
        self.cycle, self.observed = 0, None
        self.start = self.terms.make("start", None)
        self.state = {}
        self.memory_fields = []
        if len(ir["states"]) > 16384:
            raise NotImplementedError("nested record groups need an additional layout adapter")
        for index, field in enumerate(ir["states"]):
            if field["sort"]["kind"] == "memory":
                if field["sort"]["address_width"] != 4 or field["sort"]["width"] != 32:
                    raise NotImplementedError("only the two input memories are supported")
                name = "ab"[len(self.memory_fields)]
                self.memory_fields.append(field["field"])
                self.state[field["field"]] = self.terms.make("memory", -1, extra=name)
            else:
                if field["initial"]["mask"]:
                    raise NotImplementedError("known initial register bits need a parameterization lemma")
                group=index//128 if len(ir["states"])>128 else None
                self.state[field["field"]] = self.terms.make("raw", field["sort"]["width"], extra=(group, field["field"]))
        if len(self.memory_fields) != 2:
            raise ValueError("expected exactly two read-only input memories")
        self.history = [self.snapshot()]
        self.created = []
        self.node_values = []

    def snapshot(self):
        return self.state.copy(), self.start, self.observed

    def advance(self):
        terms = self.terms
        begin = len(terms.nodes)
        control = {"reset": terms.const(self.cycle < 4, 1),
                   "in3_valid": terms.apply("ite", 1, [self.start, terms.const(1, 1), terms.const(0, 1)]),
                   "clock": terms.const(1, 1), "in2_st0_done_valid": terms.const(0, 1),
                   "out0_ready": terms.const(1, 1), "in2_st0_ready": terms.const(1, 1)}
        inputs = {f["field"]: control[f["name"]] for f in self.ir["inputs"]}
        values = []
        for node in self.ir["nodes"]:
            op, width = node["op"], node["sort"].get("width")
            args = [values[i] for i in node["args"]]
            if op == "constant": value = terms.const(node["value"], width)
            elif op == "state": value = self.state[node["field"]]
            elif op == "input": value = inputs[node["field"]]
            elif op == "select": value = terms.make("read", 32, [args[1]], extra=args[0].extra)
            else: value = terms.apply(op, width, args, offset=node.get("offset"))
            values.append(value)
        outputs = {f["name"]: values[f["node"]] for f in self.ir["outputs"]}
        self.state = {f["field"]: values[f["node"]] for f in self.ir["states"]}
        if self.cycle < 4:
            self.start, self.observed = terms.const(True, None), None
        else:
            ready = terms.apply("=", None, [outputs["in3_ready"], terms.const(0, 1)])
            self.start = terms.apply("ite", None, [ready, self.start, terms.const(False, None)])
            valid = outputs["in2_st0_valid"]
            if valid.op != "constant":
                raise NotImplementedError(f"symbolic acceptance at cycle {self.cycle}")
            self.observed = outputs["in2_st0"] if valid.extra else None
        self.cycle += 1
        self.history.append(self.snapshot())
        self.created.append(list(range(begin, len(terms.nodes))))
        self.node_values.append(values)


def emit(trace, out, design="Baseline", limit=None, core_source=None):
    """Emit a reviewable candidate trace and independent transition obligations."""
    out.mkdir(parents=True, exist_ok=True)
    core = f"Task2.Imported.{design}Core"
    adapter = f"Task2.Imported.{design}Adapter"
    namespace = f"Task2.Imported.{design}Trace"
    params = "(a b : Task2.Words) (raw : " + core + ".State) (seedStart : Bool)"
    call = " a b raw seedStart"

    def ref(term):
        if term.op == "constant":
            return ("true" if term.extra else "false") if term.width is None else f"({term.extra}#{term.width})"
        if term.op == "raw": return f"raw.{term.extra[1]}" if term.extra[0] is None else f"raw.g{term.extra[0]}.{term.extra[1]}"
        if term.op == "start": return "seedStart"
        if term.op == "memory": return f"(fun address => {term.extra} ⟨address.toNat, address.isLt⟩)"
        return f"(v{term.number}{call})"

    def expression(term):
        a = [ref(x) for x in term.args]
        if term.op in ("bvand", "bvor", "bvadd", "bvmul"):
            op = {"bvand": " &&& ", "bvor": " ||| ", "bvadd": " + ", "bvmul": " * "}[term.op]
            return "(" + op.join(a) + ")"
        if term.op == "=": return f"({a[0]} == {a[1]})"
        if term.op == "ite": return f"(if {a[0]} then {a[1]} else {a[2]})"
        if term.op == "bvnot": return f"(~~~{a[0]})"
        if term.op == "extract": return f"(BitVec.extractLsb' {term.extra} {term.width} {a[0]})"
        if term.op == "concat": return f"({a[0]} ++ {a[1]})"
        if term.op == "zero_extend": return f"(BitVec.setWidth {term.width} {a[0]})"
        if term.op == "bvshl": return f"({a[0]} <<< (Nat.min {term.width} {a[1]}.toNat))"
        if term.op == "bvsgt": return f"(BitVec.slt {a[1]} {a[0]})"
        if term.op == "read": return f"({term.extra} ⟨{a[0]}.toNat, {a[0]}.isLt⟩)"
        raise NotImplementedError(term.op)

    lines = [f"import {adapter}", "set_option maxHeartbeats 0", "set_option maxRecDepth 65536",
             "set_option linter.unusedVariables false", f"namespace {namespace}",
             "@[simp] theorem mask1_left (x : BitVec 1) : 1#1 &&& x = x := BitVec.allOnes_and",
             "@[simp] theorem mask1_right (x : BitVec 1) : x &&& 1#1 = x := BitVec.and_allOnes",
             "theorem join_low {w n : Nat} (x : BitVec w) :",
             "    x.extractLsb' n 1 ++ x.extractLsb' 0 n = x.extractLsb' 0 (1+n) :=",
             "  BitVec.extractLsb'_append_extractLsb'_eq_extractLsb' (by omega)"]
    # Explicit result widths match the importer's literal-width HAppend instances.
    for size in range(1, 32):
        lines += [f"theorem join{size} {{w : Nat}} (x : BitVec w) :",
                  f"    (x.extractLsb' {size} 1 ++ x.extractLsb' 0 {size} : BitVec {size+1}) = x.extractLsb' 0 {size+1} := join_low x"]
    for term in trace.terms.nodes:
        if term.op not in ("constant", "raw", "start", "memory"):
            typ = "Bool" if term.width is None else f"BitVec {term.width}"
            lines.append(f"noncomputable def v{term.number} {params} : {typ} := {expression(term)}")
    chunks, chunk_names = [], {}
    if core_source:
        source = Path(core_source).read_text()
        for match in re.finditer(r'@\[noinline\] def c2lChunk(\d+) .*? :=\n(.*?)(?=\n\nabbrev|\n\ndef evaluate)', source, re.S):
            number, body = int(match[1]), match[2]
            header = match[0].splitlines()[0]
            incoming = [int(s) for s in re.findall(r'\(c(\d+) :', header)]
            returned = body.splitlines()[-1].strip()
            ids = [int(s) for s in re.findall(r'\bn(\d+)\b', returned)]
            chunks.append((number, incoming, returned, ids))
        if not chunks:
            raise ValueError("no imported chunks found")
        outputs_seen = {}
        for cycle, values in enumerate(trace.node_values):
            for number, incoming, returned, ids in chunks:
                key = number, tuple(values[i].number for i in ids)
                if key in outputs_seen:
                    chunk_names[cycle, number] = outputs_seen[key]
                    continue
                name = f"chunk{cycle}_{number}"
                chunk_names[cycle, number] = outputs_seen[key] = name
                expression = re.sub(r'\bn(\d+)\b', lambda m: ref(values[int(m[1])]), returned)
                lines.append(f"noncomputable def {name} {params} : {core}.C2LChunk{number} := {expression}")
    for cycle, (state, start, observed) in enumerate(trace.history):
        groups = []
        fields = list(state)
        for group in range((len(fields)+127)//128):
            bindings = ", ".join(f"{field} := {ref(state[field])}" for field in fields[group*128:(group+1)*128])
            groups.append(f"g{group} := {{ {bindings} }}" if len(fields)>128 else bindings)
        obs = "none" if observed is None else f"some {ref(observed)}"
        lines.append(f"noncomputable def state{cycle} {params} : {adapter}.State :=\n  {{ raw := {{ " + ", ".join(groups) + f" }}, cycles := {cycle}, start := {ref(start)}, observed := {obs} }}")
    lines.append(f"end {namespace}")
    (out / f"{design}Trace.lean").write_text("\n".join(lines)+"\n")
    if chunks:
        certificates, assignments, batches = {}, {}, []
        def chunk_call(cycle, number):
            return f"({chunk_names[cycle, number]}{call})"
        def equation(cycle, number, incoming):
            argument = " ".join(chunk_call(cycle, i) for i in incoming)
            return f"{core}.c2lChunk{number} ({adapter}.inputs (state{cycle}{call})) (state{cycle}{call}).raw {argument} = {chunk_names[cycle, number]}{call}"
        def header(imports):
            return [f"import {i}" for i in imports+["Task2.ProofTools"]] + ["set_option maxHeartbeats 0", "set_option maxRecDepth 65536",
                    "set_option linter.unusedSimpArgs false", "set_option linter.unusedVariables false", f"namespace {namespace}"]
        for cycle, values in enumerate(trace.node_values[:limit]):
            for number, incoming, returned, ids in chunks:
                dependency_ids = {a for n in trace.ir["nodes"][number*128:(number+1)*128]
                                  for a in n["args"] if a//128 != number}
                dependency_ids.update(n["id"] for n in trace.ir["nodes"][number*128:(number+1)*128] if n["op"] in ("input", "state"))
                key = number, tuple(values[i].number for i in sorted(dependency_ids))
                if key in certificates:
                    assignments[cycle, number] = certificates[key]
                    continue
                serial = len(certificates)
                batch = serial//100
                certificate = f"cut{cycle}_{number}", batch
                assignments[cycle, number] = certificates[key] = certificate
                if batch == len(batches): batches.append(header([f"Task2.Imported.{design}Trace"]))
                defs = [f"{core}.c2lChunk{number}", f"{adapter}.inputs", f"state{cycle}", chunk_names[cycle, number]]
                defs += [chunk_names[cycle, i] for i in incoming]
                used = {v.number for v in values[number*128:(number+1)*128]}
                used.update(values[i].number for i in dependency_ids)
                def visit(term):
                    for arg in term.args:
                        if arg.number not in used:
                            used.add(arg.number)
                            visit(arg)
                for i in list(used): visit(trace.terms.nodes[i])
                defs += [f"v{i}" for i in sorted(used) if trace.terms.nodes[i].op not in ("constant", "raw", "start", "memory")]
                defs += ["BitVec.extractLsb'_append_extractLsb'_eq_extractLsb'",
                         "BitVec.extractLsb'_extractLsb'_of_le", "BitVec.extractLsb'_eq_self"]
                proof = [f"theorem cut{cycle}_{number} {params} :",
                         f"    {equation(cycle, number, incoming)} := by",
                         "  simp (config := { maxSteps := 100000 }) [" + ", ".join(defs) + "]",
                         "  all_goals simp only [" + ", ".join(f"join{i}" for i in range(1,32)) + ", BitVec.extractLsb'_eq_self]",
                         f"#print axioms cut{cycle}_{number}"]
                concatenations=[values[n['id']] for n in trace.ir['nodes'][number*128:(number+1)*128] if n['op']=='concat']
                if concatenations and all(t.op=='constant' for t in concatenations):
                    # Closed zero-write masks trigger slow generic simplifier rules;
                    # reflexivity gives the kernel a much smaller certificate.
                    proof=proof[:2]+["  kernel_rfl",proof[-1]]
                batches[batch] += proof
        for batch, proof in enumerate(batches):
            proof.append(f"end {namespace}")
            (out / f"{design}Cuts{batch}.lean").write_text("\n".join(proof)+"\n")
        for cycle, values in enumerate(trace.node_values[:limit]):
            required = sorted({assignments[cycle, number][1] for number, *_ in chunks})
            proof = header([f"Task2.Imported.{design}Cuts{i}" for i in required])
            proof += [f"theorem transition{cycle} {params} :",
                      f"    {adapter}.step (state{cycle}{call}) = state{cycle+1}{call} := by"]
            for number, incoming, *_ in chunks:
                name, batch = assignments[cycle, number]
                proof += [f"  have h{number} : {equation(cycle, number, incoming)} := by",
                          f"    kernel_exact {name}{call}"]
            proof += ["  simp only [" + ", ".join([f"{adapter}.step", f"{core}.evaluate"]+[f"h{i}" for i, *_ in chunks])+"]",
                      "  kernel_rfl", f"#print axioms transition{cycle}", f"end {namespace}"]
            (out / f"{design}Transition{cycle}.lean").write_text("\n".join(proof)+"\n")
        for first in range(0, trace.cycle, 20):
            required = sorted({assignments[cycle, number][1] for cycle in range(first,min(first+20,trace.cycle)) for number, *_ in chunks})
            proof = header([f"Task2.Imported.{design}Cuts{i}" for i in required])
            for cycle in range(first,min(first+20,trace.cycle)):
                original=(out/f"{design}Transition{cycle}.lean").read_text().splitlines()
                start=next(i for i,s in enumerate(original) if s.startswith("theorem "))
                proof+=original[start:-1]
            proof.append(f"end {namespace}")
            (out/f"{design}Transitions{first//20}.lean").write_text("\n".join(proof)+"\n")
        # A separately checked arithmetic obligation for the final symbolic word.
        if trace.observed is not None:
            used=set()
            def visit_final(term):
                if term.number in used:return
                used.add(term.number)
                for arg in term.args:visit_final(arg)
            visit_final(trace.observed)
            defs=[f"v{i}" for i in sorted(used) if trace.terms.nodes[i].op not in ("constant","raw","start","memory")]
            proof=header([f"Task2.Imported.{design}Trace"])
            proof += [f"theorem final_word {params} : {ref(trace.observed)} = Task2.dot32 a b := by",
                      "  simp ["+", ".join(defs+["Task2.dot32","List.finRange","List.ofFn","Fin.foldr","Fin.foldr.loop","BitVec.mul_comm"])+"]",
                      "#print axioms final_word",f"end {namespace}"]
            (out/f"{design}FinalArithmetic.lean").write_text("\n".join(proof)+"\n")
        proof=header([f"Task2.Imported.{design}Trace"])
        groups=(len(trace.ir['states'])+127)//128
        decompose=(["  cases raw"] if groups==1 else
                   ["  rcases raw with ⟨"+", ".join(f"g{i}" for i in range(groups))+"⟩"]+
                   [f"  cases g{i}" for i in sorted({j//128 for j,f in enumerate(trace.ir['states']) if f['field'] in trace.memory_fields})])
        proof += [f"theorem initial_parameterization (a b : Task2.Words) (s : {adapter}.State) (h : {adapter}.initial a b s) :",
                  f"    s = state0 a b s.raw s.start := by",
                  "  rcases s with ⟨raw, cycles, start, observed⟩",
                  "  obtain ⟨hc, ho, _, ha, hb⟩ := h", "  dsimp only at hc ho ha hb",
                  "  subst cycles", "  subst observed"]+decompose+[
                  "  simp_all [state0]", "#print axioms initial_parameterization",f"end {namespace}"]
        (out/f"{design}Initial.lean").write_text("\n".join(proof)+"\n")
        proof=header(["Mathlib.Tactic.IntervalCases","Task2.Source",f"Task2.Imported.{design}Initial",f"Task2.Imported.{design}FinalArithmetic"]+
                     [f"Task2.Imported.{design}Transitions{i}" for i in range((trace.cycle+19)//20)])
        proof += [f"noncomputable def traceAt {params} (n : Nat) : {adapter}.State :=", "  match n with"]
        proof += [f"  | {i} => state{i}{call}" for i in range(trace.cycle)]
        proof += [f"  | _ => state{trace.cycle}{call}",
                  f"theorem first_result {params} : Task2.FirstResult Task2.Imported.{design.lower()} (state0{call}) {trace.cycle} (Task2.dot32 a b) := by",
                  f"  apply Task2.firstResult_of_trace Task2.Imported.{design.lower()} (traceAt{call}) {trace.cycle} (Task2.dot32 a b)",
                  "  · intro n hn", "    interval_cases n"]
        proof += [f"    · exact transition{i}{call}" for i in range(trace.cycle)]
        proof += [f"  · change (state{trace.cycle}{call}).observed = some (Task2.dot32 a b)",
                  "    exact congrArg some (final_word a b raw seedStart)",
                  "  · intro n hn", "    interval_cases n <;> rfl",
                  f"theorem correct : Task2.Implements Task2.Imported.{design.lower()} Task2.sourceEval := by",
                  "  constructor", f"  · exact {adapter}.initial_exists",f"  · refine ⟨{trace.cycle}, ?_⟩",
                  "    intro a b s hs", f"    refine ⟨{trace.cycle}, Task2.dot32 a b, le_rfl, ?_, Task2.source_agrees a b⟩",
                  "    have hp := initial_parameterization a b s hs", "    rw [hp]",
                  "    exact first_result a b s.raw s.start", "#print axioms first_result", "#print axioms correct",f"end {namespace}"]
        (out/f"{design}TraceCorrect.lean").write_text("\n".join(proof)+"\n")
        (out / "certificate-index.json").write_text(json.dumps({"unique_cuts":len(certificates),"batches":len(batches),"cycles":trace.cycle,"transition_batches":(trace.cycle+19)//20,"definitions":f"{design}Trace.lean"},indent=2)+"\n")
        return
    for cycle, created in enumerate(trace.created[:limit]):
        names = [f"{adapter}.step", f"{adapter}.inputs", f"{core}.evaluate"]
        names += [f"{core}.c2lChunk{i}" for i in range((len(trace.ir['nodes'])+127)//128)]
        names += [f"state{cycle}", f"state{cycle+1}"]
        # Previous slices must be visible when the hardware reassembles a word.
        names += [f"v{t.number}" for t in trace.terms.nodes if t.number in created or (t.number < min(created, default=0) and t.op in ("extract", "concat"))
                  if t.op not in ("constant", "raw", "start", "memory")]
        proof = [f"import Task2.Imported.{design}Trace", "set_option maxHeartbeats 0",
                 "set_option maxRecDepth 65536", f"namespace {namespace}",
                 f"theorem transition{cycle} {params} :",
                 f"    {adapter}.step (state{cycle}{call}) = state{cycle+1}{call} := by",
                 "  simp (config := { maxSteps := 1000000 }) [" + ", ".join(names) + "]",
                 f"#print axioms transition{cycle}", f"end {namespace}"]
        (out / f"Transition{cycle}.lean").write_text("\n".join(proof)+"\n")


def prove_design(out, design, source_result, hardware_result, timeout=600, workers=8):
    """Build all proof layers freshly; status requires compilation AND axiom audits."""
    from run import ROOT, execute, artifact, audit_axioms
    if workers < 1 or workers > 16:
        raise ValueError("workers must be between 1 and 16")
    name = design.title()
    folder = out / "proof" / design
    folder.mkdir(parents=True, exist_ok=True)
    runs = []
    bindings = {**source_result["artifacts"], **hardware_result["artifacts"]}
    lean_path = subprocess.check_output(["lake", "env", "printenv", "LEAN_PATH"], cwd=ROOT, text=True).strip()
    env = {**os.environ, "LEAN_PATH": lean_path}
    lean = subprocess.check_output(["sh", "-c", "command -v lean"], text=True).strip()
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    if not re.search(r"version 4\.35\.0(?:\D|$)", version):
        raise ValueError("Lean 4.35.0 is required")
    library = ROOT / ".lake/build/lib/lean"

    def compile_file(path, module, audits=()):
        target = library.joinpath(*module.split(".")).with_suffix(".olean")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Failed attempts cannot leave an old object eligible for a later stage.
        target.unlink(missing_ok=True)
        result = execute([lean, "-o", str(target), str(path)], folder/(path.stem+".log"), env=env, timeout=timeout)
        if result["status"] == "prepared":
            try:
                output=Path(result["log"]["path"]).read_text()
                result["axioms"]={theorem:audit_axioms(output,theorem) for theorem in audits}
                result["status"]="proved" if audits else "prepared"
            except ValueError as error:
                result["status"]="failed";result["error"]=str(error)
        result["source"]=artifact(path)
        return result

    def stopped():
        failures=[r for r in runs if r["status"] not in ("prepared","proved")]
        if failures:
            return {"status":failures[0]["status"],"claim":"no complete hardware theorem established in this run",
                    "design":design,"runs":runs,"artifacts":bindings}

    runs.append(execute(["lake","build","Task2.Source","Task2.Hardware"],folder/"library.log",timeout=timeout))
    if stopped():return stopped()
    for path,module in [(ROOT/"Task2/Trace.lean","Task2.Trace"),(ROOT/"Task2/ProofTools.lean","Task2.ProofTools"),
                        (Path(hardware_result['artifacts']['imported_core']['path']),f"Task2.Imported.{name}Core"),
                        (Path(hardware_result['artifacts']['device_adapter']['path']),f"Task2.Imported.{name}Adapter")]:
        runs.append(compile_file(path,module))
        if stopped():return stopped()
    trace=SymbolicTrace(json.loads(Path(hardware_result["artifacts"]["functional_ir"]["path"]).read_text()))
    for _ in range(10000):
        trace.advance()
        if trace.observed is not None:break
    if trace.observed is None:
        raise NotImplementedError("symbolic controller did not reach a result within the generation budget")
    emit(trace,folder,design=name,core_source=hardware_result['artifacts']['imported_core']['path'])
    index=json.loads((folder/"certificate-index.json").read_text())
    runs.append(compile_file(folder/f"{name}Trace.lean",f"Task2.Imported.{name}Trace"))
    if stopped():return stopped()

    def compile_batch(pair):
        kind,i=pair
        path=folder/f"{name}{kind}{i}.lean"
        names=re.findall(r'^theorem (\w+) ',path.read_text(),re.M)
        if not names:raise ValueError("empty proof batch")
        return compile_file(path,f"Task2.Imported.{name}{kind}{i}",
                            [f"Task2.Imported.{name}Trace.{s}" for s in names])
    for kind,total in [("Cuts",index["batches"]),("Transitions",index["transition_batches"])]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            runs.extend(pool.map(compile_batch,[(kind,i) for i in range(total)]))
        if stopped():return stopped()
    for suffix,theorems in [("Initial",["initial_parameterization"]),("FinalArithmetic",["final_word"]),
                             ("TraceCorrect",["first_result","correct"])]:
        runs.append(compile_file(folder/f"{name}{suffix}.lean",f"Task2.Imported.{name}{suffix}",
                                 [f"Task2.Imported.{name}Trace.{s}" for s in theorems]))
        if stopped():return stopped()
    public=ROOT/f"Task2/{name}.lean"
    runs.append(compile_file(public,f"Task2.{name}"))
    if stopped():return stopped()
    audit=folder/"PublicAudit.lean"
    from public_claim import audit_text
    audit.write_text(audit_text(design))
    result=execute([lean,str(audit)],folder/"public-audit.log",env=env,timeout=timeout)
    runs.append(result)
    if stopped():return stopped()
    axioms=audit_axioms(Path(result["log"]["path"]).read_text(),f"Task2.{design}_correct")
    for path in sorted(folder.glob("*.lean")):
        bindings["certificate_"+path.stem]=artifact(path)
    for path in [ROOT/"Task2/WordDot.lean",ROOT/"Task2/Hardware.lean",ROOT/"Task2/Trace.lean",
                 ROOT/"Task2/ProofTools.lean",public,ROOT/"scripts/prove_trace.py",ROOT/"scripts/run.py",ROOT/"scripts/public_claim.py"]:
        bindings["proof_support_"+path.name]=artifact(path)
    return {"status":"proved","design":design,"claim":f"Task2.{design}_correct : Implements Imported.{design} sourceEval",
            "scope":"all pairs of 16 complete int32 word vectors; every permitted raw initial state; first accepted payload",
            "completion_bound_edges":trace.cycle,"includes_reset_edges":4,"axioms":axioms,
            "lean_version":version,"obligations":index,"workers":workers,"runs":runs,"artifacts":bindings,
            "trust_boundary":json.loads((ROOT/"contract.json").read_text())["trust_boundary"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cycles", type=int, default=436)
    p.add_argument("--core-source", type=Path)
    args = p.parse_args()
    trace = SymbolicTrace(json.loads(args.ir.read_text()))
    for _ in range(args.cycles): trace.advance()
    emit(trace, args.out, core_source=args.core_source)
    print(f"Proposed {trace.cycle} transitions, {len(trace.terms.nodes)} symbolic terms; Lean checking still required")


if __name__ == "__main__":
    main()
