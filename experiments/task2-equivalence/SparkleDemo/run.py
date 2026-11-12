#!/usr/bin/env python3
"""Import the original Task 2 RTL with Sparkle and compare fresh traces."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent
INPUT_MEMORIES = (
    "handshake_memory0._handshake_memory_5",
    "handshake_memory1._handshake_memory_4",
)
PORTS = ("reset", "in3_valid", "in3_ready", "out0_valid",
         "in2_st0_done_ready", "in2_st0_valid", "in2_st0_ready")


def file_identity(path):
    p = Path(path).resolve()
    return {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def verify_identity(identity):
    if file_identity(identity["path"])["sha256"] != identity["sha256"]:
        raise ValueError(f"source identity changed: {identity['path']}")


def validate_input_memories(module):
    memories = []
    for name in INPUT_MEMORIES:
        cell = module["cells"].get(name)
        if cell is None or cell["type"] != "$mem_v2":
            raise ValueError(f"missing input memory: {name}")
        params = cell["parameters"]
        if int(params["WR_PORTS"], 2) != 0:
            raise ValueError(f"input memory must be read-only: {name}")
        if (int(params["SIZE"], 2), int(params["WIDTH"], 2),
                int(params["RD_PORTS"], 2)) != (16, 32, 1):
            raise ValueError(f"expected a 16 by 32 input memory: {name}")
        memories.append(name)
    return memories


def compare_traces(left, right, expected):
    if len(left) != len(right):
        raise ValueError(f"trace length mismatch: {len(left)} / {len(right)}")
    events = []
    for cycle, (a, b) in enumerate(zip(left, right)):
        if a["cycle"] != cycle or b["cycle"] != cycle:
            raise ValueError(f"nonconsecutive cycle at {cycle}")
        for port in PORTS:
            if a[port] not in (0, 1) or b[port] not in (0, 1):
                raise ValueError(f"nonbinary {port} at cycle {cycle}")
            if a[port] != b[port]:
                raise ValueError(f"{port} differs at cycle {cycle}: {a[port]} / {b[port]}")
        if not a["reset"] and a["in2_st0_valid"] and a["in2_st0_ready"]:
            if a["in2_st0"] != expected or b["in2_st0"] != expected:
                raise ValueError(f"accepted payload mismatch at cycle {cycle}")
            events.append(cycle)
    if len(events) != 1 or events[0] != len(left) - 1:
        raise ValueError("expected exactly one completion on the final trace row")
    return {"edges": len(left), "payload": expected}


def read_trace(path):
    with Path(path).open() as stream:
        return [{key: int(value) for key, value in row.items()}
                for row in csv.DictReader(stream)]


def compiler_for(env):
    compiler = shutil.which("cc", path=env["PATH"]) or shutil.which("gcc", path=env["PATH"])
    if compiler is None:
        raise ValueError("no C compiler in the simulation environment")
    return compiler


def execute(command, log, records, env=None, timeout=600):
    started = time.monotonic()
    with Path(log).open("w") as stream:
        result = subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                                stdout=stream, stderr=subprocess.STDOUT,
                                timeout=timeout)
    record = {"command": [str(x) for x in command], "returncode": result.returncode,
              "seconds": round(time.monotonic() - started, 6), "log": file_identity(log)}
    records.append(record)
    if result.returncode:
        raise RuntimeError(f"command failed; see {log}\n" + Path(log).read_text()[-4000:])


def ansi_header(source, module):
    """Restate Yosys's non-ANSI port declarations using its own JSON schema."""
    ports = []
    for name, port in module["ports"].items():
        width = len(port["bits"])
        size = f"[{width - 1}:0] " if width > 1 else ""
        ports.append(f"  {port['direction']} {size}{name}")
    match = re.search(r"module\s+task2\s*\([^;]*\);", source)
    if match is None:
        raise ValueError("expected one Yosys task2 module header")
    body = source[match.end():]
    body = re.sub(r"(?m)^\s*(?:input|output|inout)\s+[^;]+;", "", body)
    return source[:match.start()] + "module task2(\n" + ",\n".join(ports) + "\n);" + body


def prepare_frontend(out, pins, records):
    source = Path(pins["rtl"]["path"])
    for name, digest in pins["rtl"]["files"].items():
        verify_identity({"path": str(source / name), "sha256": digest})
    frontend = out / "frontend.ys"
    frontend.write_text("\n".join([
        f"read_slang --top main --no-proc --no-synthesis-define --no-default-translate-off-format -f {source/'sources.f'}",
        "hierarchy -check -top main", "proc -noopt", "flatten", "opt_clean",
        "memory_collect", f"write_json {out/'premap.json'}", ""]))
    execute([pins["yosys"], "-Q", "-T", "-m", "slang", "-s", frontend],
            out / "frontend.log", records)
    module = json.loads((out / "premap.json").read_text())["modules"]["main"]
    validate_input_memories(module)
    clock = module["ports"]["clock"]["bits"]
    for name, cell in module["cells"].items():
        if cell["type"] == "$dff" and (cell["connections"]["CLK"] != clock or
                int(cell["parameters"]["CLK_POLARITY"], 2) != 1):
            raise ValueError(f"unsupported clock on {name}")
    lines = [f"read_json {out/'premap.json'}", "memory_map -keepdc", "cd main"]
    ports = []
    for prefix, memory in zip(("a", "b"), INPUT_MEMORIES):
        for index in range(16):
            port = f"ram_{prefix}_{index}"
            lines.append(f"rename {memory}[{index}] {port}")
            ports.append(port)
    lines += ["expose -input " + " ".join(f"w:{p}" for p in ports),
              "opt_expr", "opt_muxtree", "opt_clean", "rename -unescape",
              "rename -top task2", "check -assert",
              f"write_json {out/'normalized.json'}",
              f"write_verilog -noattr -nodec -simple-lhs {out/'yosys-task2.v'}", ""]
    script = out / "normalize.ys"
    script.write_text("\n".join(lines))
    execute([pins["yosys"], "-Q", "-T", "-s", script], out / "normalize.log", records)
    module = json.loads((out / "normalized.json").read_text())["modules"]["task2"]
    normalized = ansi_header((out / "yosys-task2.v").read_text(), module)
    (out / "task2.sv").write_text(normalized)
    if re.search(r"\b\d+'[bhd][0-9a-f_]*[xz]", normalized, re.IGNORECASE):
        raise ValueError("normalized RTL contains explicit unknown literals")
    return source


def c_harness(cases):
    lines = ['\n#include <stdio.h>', 'int main(int argc, char **argv) {',
             '  if (argc != 2) return 2;', '  FILE *out;', '  char path[4096];']
    for index, case in enumerate(cases):
        lines += ['  {', '    struct task2 s; memset(&s, 0, sizeof(s));', '    sparkle_task2_reset(&s);',
                  f'    snprintf(path, sizeof(path), "%s/case-{index}-c.csv", argv[1]);',
                  '    out = fopen(path, "w"); if (!out) return 3;',
                  '    fprintf(out, "cycle,reset,in3_valid,in3_ready,out0_valid,in2_st0_done_ready,in2_st0_valid,in2_st0_ready,in2_st0\\n");']
        for prefix, words in zip(("a", "b"), case["input_words"]):
            for k, word in enumerate(words):
                lines.append(f'    s.ram_{prefix}_{k} = {word}u;')
        lines += ['    s.in3_valid = 0;', '    s.out0_ready = 1; s.in2_st0_ready = 1; s.in2_st0_done_valid = 0;',
                  '    int completed = 0;', '    for (int cycle = 0; cycle < 1000; cycle++) {',
                  '      s.reset = cycle < 4;', '      sparkle_task2_eval(&s);',
                  '      fprintf(out, "%d,%u,%u,%u,%u,%u,%u,1,%u\\n", cycle, (unsigned)s.reset, (unsigned)s.in3_valid, (unsigned)s.in3_ready, (unsigned)s.out0_valid, (unsigned)s.in2_st0_done_ready, (unsigned)s.in2_st0_valid, (unsigned)s.in2_st0);',
                  '      if (!s.reset && s.in2_st0_valid) { completed = 1; break; }',
                  '      unsigned next_start = s.reset ? 1 : (s.in3_ready ? 0 : s.in3_valid);',
                  '      sparkle_task2_tick(&s); s.in3_valid = next_start;',
                  '    }', '    fclose(out); if (!completed) return 4;', '  }']
    return "\n".join(lines + ['  return 0;', '}']) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build",
                        help="work directory; the native proof requires SparkleDemo/build")
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT):
        parser.error("output must stay under SparkleDemo/")
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / "result.json"
    result_path.unlink(missing_ok=True)
    (out / "universal-result.json").unlink(missing_ok=True)
    if out != ROOT / "build":
        parser.error("the native model and proof use SparkleDemo/build; omit --out")
    pins = json.loads((ROOT / "pins.json").read_text())
    version = subprocess.check_output(["lean", "--version"], text=True).strip()
    if not version.startswith(f"Lean (version {pins['lean']},"):
        raise ValueError(f"Sparkle requires Lean {pins['lean']}; got {version}")
    cases = json.loads((ROOT / "controls.json").read_text())
    for case in cases:
        words = case["input_words"]
        if len(words) != 2 or any(len(v) != 16 for v in words):
            raise ValueError("controls require two length-16 word vectors")
        expected = sum(a * b for a, b in zip(*words)) % 2**32
        if case["expected_output_words"] != [[expected]]:
            raise ValueError("incorrect modular reference result")
    records = []
    source = prepare_frontend(out, pins, records)
    print("[1/4] Fresh RTL frontend and read-only input-memory lift passed", flush=True)
    execute(["lake", "build", "sparkle-import", "native-smoke", "NativeExport"], out / "lake-build.log", records)
    dependency = ROOT / ".lake/packages/sparkle"
    revision = subprocess.check_output(["git", "-C", str(dependency), "rev-parse", "HEAD"], text=True).strip()
    if revision != pins["sparkle"]["revision"]:
        raise ValueError("Sparkle dependency revision changed")
    subprocess.run(["git", "-C", str(dependency), "diff", "--exit-code", "HEAD"], check=True,
                   stdout=subprocess.DEVNULL)
    execute([ROOT / ".lake/build/bin/native-smoke"], out / "native-smoke.log", records)
    execute([ROOT / ".lake/build/bin/sparkle-import", out / "task2.sv", out],
            out / "sparkle-import.log", records)
    execute(["lake", "env", "lean", "ExportTask2.lean"], out / "native-export.log", records)
    execute(["lake", "build", "native-traces"], out / "native-build.log", records)
    execute([ROOT / ".lake/build/bin/native-traces", ROOT / "controls.json", out],
            out / "native-traces.log", records)
    print("[2/4] Native Lean model emitted by upstream Sparkle reflection and executed", flush=True)
    simulation_env = dict(os.environ)
    simulation_env["PATH"] = ":".join(str(Path(p) / "bin") for p in pins["simulation_build_inputs"]) + ":" + os.environ["PATH"]
    c_source = out / "task2-sim.c"
    c_source.write_text((out / "sparkle.c").read_text() + c_harness(cases))
    execute([compiler_for(simulation_env), "-O2", "-std=c11", c_source, "-o", out / "sparkle-sim"],
            out / "c-build.log", records, env=simulation_env)
    execute([out / "sparkle-sim", out], out / "c-run.log", records)
    verilator = next(Path(p) / "bin/verilator" for p in pins["simulation_build_inputs"] if "verilator" in p)
    execute([verilator, "--binary", "--timing", "--language", "1800-2017", "-Wno-fatal",
             "-top", "tb_control", "-Mdir", out / "obj_dir", "-o", "sim_control",
             "-f", source / "sources.f", ROOT / "control_tb.sv"],
            out / "verilator-build.log", records, env=simulation_env)
    print("[3/4] Sparkle C and original-RTL Verilator simulations built", flush=True)
    comparison = []
    for index, case in enumerate(cases):
        files = []
        for label, words in zip(("a", "b"), case["input_words"]):
            path = out / f"case-{index}-{label}.hex"
            path.write_text("".join(f"{word:08x}\n" for word in words))
            files.append(path)
        expected = case["expected_output_words"][0][0]
        rtl = out / f"case-{index}-rtl.csv"
        execute([out / "obj_dir/sim_control", f"+A={files[0]}", f"+B={files[1]}",
                 f"+TRACE={rtl}", f"+EXPECTED={expected:08x}"], out / f"case-{index}-rtl.log", records)
        golden = read_trace(rtl)
        evidence = {"case": index}
        for backend in ("lean", "c"):
            evidence[backend] = compare_traces(golden, read_trace(out / f"case-{index}-{backend}.csv"), expected)
        if len(golden) != 436:
            raise ValueError("Task 2 first result did not arrive after 436 edges")
        comparison.append(evidence)
        print(f"case {index}: RTL = Sparkle Lean = Sparkle C; payload={expected}; 436 edges", flush=True)
    # Exercise the comparator on a real accepted output mutation.
    wrong = read_trace(out / "case-6-lean.csv")
    wrong[-1]["in2_st0"] ^= 1
    try:
        compare_traces(read_trace(out / "case-6-rtl.csv"), wrong, 816)
    except ValueError as error:
        mutation = str(error)
    else:
        raise ValueError("payload mutation was incorrectly accepted")
    # Only outputs emitted by this stage belong in its evidence manifest.
    # Proof files from an earlier run may coexist in the output directory.
    artifact_paths = [out / name for name in (
        "frontend.ys", "frontend.log", "premap.json", "normalize.ys", "normalize.log",
        "normalized.json", "yosys-task2.v", "task2.sv", "sparkle-ir.txt",
        "native/Task2RTL.lean", "native/Task2RTL.json",
        "sparkle.c", "roundtrip.sv", "lake-build.log", "native-smoke.log",
        "native-export.log", "native-build.log", "native-traces.log",
        "sparkle-import.log", "task2-sim.c", "c-build.log",
        "c-run.log", "sparkle-sim", "verilator-build.log", "obj_dir/sim_control")]
    for index in range(len(cases)):
        artifact_paths += [out / f"case-{index}-{suffix}" for suffix in
                           ("a.hex", "b.hex", "rtl.csv", "lean.csv", "c.csv", "rtl.log")]
    artifacts = [file_identity(p) for p in artifact_paths]
    result = {"status": "passed_controls", "universal_equivalence_proved": False,
              "sparkle": pins["sparkle"], "lean": pins["lean"], "cases": comparison,
              "model_semantics": "upstream Tools.SVParser.VerifyEmit.denote",
              "native_model": file_identity(out / "native/Task2RTL.lean"),
              "mutation_rejected": mutation, "runs": records, "artifacts": artifacts,
              "inputs": [file_identity(ROOT / p) for p in (
                  "pins.json", "controls.json", "run.py", "Import.lean", "NativeExport.lean", "control_tb.sv",
                  "lean-toolchain", "lakefile.lean", "lake-manifest.json", "NativeSmoke.lean",
                  "NativeTraces.lean", "ExportTask2.lean", "tests/fixtures/native_counter.sv",
                  "tests/fixtures/wide_registers.sv")]}
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"[4/4] SPARKLE_TASK2_CONTROLS_PASS: {result_path}")


if __name__ == "__main__":
    main()
