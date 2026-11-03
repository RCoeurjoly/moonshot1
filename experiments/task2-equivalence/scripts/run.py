#!/usr/bin/env python3
"""Artifact-bound Task 2 experiment. A control is never a proof verdict."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
NIX = ["nix", "--extra-experimental-features", "nix-command flakes"]


def digest(path):
    path = Path(path)
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.is_dir():
        raise ValueError(f"missing artifact: {path}")
    h = hashlib.sha256()
    for child in sorted(path.rglob("*")):
        if child.is_file():
            h.update(str(child.relative_to(path)).encode() + b"\0")
            h.update(bytes.fromhex(digest(child)))
    return h.hexdigest()


def store_path(path):
    return path if path.startswith("/") else "/nix/store/" + path


def graph_entries(graph):
    return graph.get("derivations", graph)


def find_derivation(graph, name):
    matches = [(store_path(k), v) for k, v in graph_entries(graph).items()
               if v.get("env", {}).get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"expected one existing derivation for {name}, got {len(matches)}")
    return matches[0]


def artifact(path, derivation=None):
    result = {"path": str(path), "sha256": digest(path)}
    if derivation:
        result["derivation"] = derivation
    return result


def parse_interface(text):
    signature = re.search(r"func\.func\s+@(?:main|forward)\s*\((.*?)\)\s*->\s*(!torch\.vtensor<\[[^]]*\],[^>]+>)", text, re.S)
    if not signature:
        raise ValueError("cannot determine compiler input interface")
    def tensor(shape, dtype):
        return {"shape": [int(x.strip()) for x in shape.split(",") if x.strip()],
                "dtype": {"si32": "int32"}.get(dtype.strip(), dtype.strip())}
    inputs = [tensor(*m) for m in re.findall(r"!torch\.vtensor<\[([^]]*)\],([^>]+)>", signature[1])]
    output = tensor(*re.search(r"\[([^]]*)\],([^>]+)>", signature[2]).groups())
    actual = {"inputs": inputs, "output": output}
    expected = json.loads((ROOT / "contract.json").read_text())["interface"]
    if actual != expected:
        raise ValueError(f"unsupported source interface: {actual}")
    return actual


def assemble_manifest(graph):
    artifacts = {}
    for key, name in [("torch", "matmul-torch.mlir"), ("baseline", "matmul-sv"), ("simulation", "matmul-sv-sim.json")]:
        drv, entry = find_derivation(graph, name)
        artifacts[key] = artifact(store_path(entry["outputs"]["out"]["path"]), drv)
    _, source = find_derivation(graph, "matmul-torch.mlir")
    command = source["env"]["buildCommand"]
    for key, expression in [("model", r'MATMUL_PY=["\']?([^"\'\s]+)'),
                            ("adapter", r'--adapter\s+["\']?([^"\'\s]+)')]:
        match = re.search(expression, command)
        if not match:
            raise ValueError(f"missing existing source provenance: {key}")
        artifacts[key] = artifact(match[1])
    simulation = json.loads(Path(artifacts["simulation"]["path"]).read_text())
    if simulation.get("status") != "PASS" or simulation.get("expected") != simulation.get("got"):
        raise ValueError("baseline simulation did not pass")
    stages = {}
    for drv, entry in graph_entries(graph).items():
        name = entry.get("env", {}).get("name", "")
        if name.startswith("matmul-"):
            stages[name] = {"derivation": store_path(drv), "outputs": {
                k: store_path(v["path"]) for k, v in entry["outputs"].items()},
                "command": entry["env"].get("buildCommand", ""),
                "build_inputs": entry["env"].get("buildInputs", "")}
    return {"schema_version": 1, "status": "prepared", "artifacts": artifacts,
            "interface": parse_interface(Path(artifacts["torch"]["path"]).read_text()),
            "simulation": simulation, "existing_stages": stages,
            "python_environment": source["env"]["buildInputs"].split()[0],
            "source_build_command": command,
            "scope": "simulation PASS is a correspondence control; no Lean hardware proof yet"}


def verify_manifest(manifest):
    for name, info in manifest["artifacts"].items():
        if digest(info["path"]) != info["sha256"]:
            raise ValueError(f"artifact identity mismatch: {name}")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def attach(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("XDG_CACHE_HOME", str(out / "cache"))
    target = str(args.task2.resolve()) + "#matmul-sv-sim"
    graph_file = out / "existing-derivations.json"
    command = NIX + ["derivation", "show", "--recursive", "--offline", "--no-write-lock-file", target]
    with graph_file.open("w") as stdout, (out / "attach.log").open("w") as stderr:
        subprocess.run(command, env=env, stdout=stdout, stderr=stderr, check=True)
    graph = json.loads(graph_file.read_text())
    _, sim = find_derivation(graph, "matmul-sv-sim.json")
    if not Path(store_path(sim["outputs"]["out"]["path"])).exists():
        with (out / "realize.log").open("w") as log:
            subprocess.run(NIX + ["build", "--no-write-lock-file", "--no-link", target],
                           env=env, stdout=log, stderr=log, check=True)
    manifest = assemble_manifest(graph)
    manifest["artifacts"]["derivation_graph"] = artifact(graph_file)
    manifest["artifacts"]["contract"] = artifact(ROOT / "contract.json")
    manifest["baseline_repository"] = str(args.task2.resolve())
    manifest["baseline_revision"] = subprocess.check_output(
        ["git", "-C", str(args.task2), "rev-parse", "HEAD"], text=True).strip()
    verify_manifest(manifest)
    write_json(out / "manifest.json", manifest)
    return {"status": "prepared", "manifest": str(out / "manifest.json"), "interface": manifest["interface"]}


def execute(command, log, env=None, timeout=600):
    """Keep every invocation and full log; timeout is an inconclusive outcome."""
    started = time.monotonic()
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as stream:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=stream,
                                   start_new_session=True)
        timed_out = False
        while True:
            pid, wait_status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                process.returncode = os.waitstatus_to_exitcode(wait_status)
                break
            if time.monotonic() - started >= timeout:
                timed_out = True
                # Stop Lake/solver descendants as well as the direct process.
                os.killpg(process.pid, signal.SIGKILL)
                _, wait_status, usage = os.wait4(process.pid, 0)
                process.returncode = os.waitstatus_to_exitcode(wait_status)
                break
            time.sleep(0.01)
        status = "timeout" if timed_out else ("prepared" if process.returncode == 0 else "failed")
        returncode = None if timed_out else process.returncode
    return {"status": status, "returncode": returncode, "command": list(map(str, command)),
            "elapsed_seconds": time.monotonic() - started, "peak_rss_kib": usage.ru_maxrss,
            "memory_measurement": "Linux wait4 ru_maxrss, maximum process RSS; not simultaneous tree sum",
            "log": artifact(log)}


def require_run(command, log, env=None, timeout=600):
    result = execute(command, log, env, timeout)
    if result["status"] != "prepared":
        raise ValueError(f'{result["status"]}: see {log}')
    return result


def audit_axioms(output, theorem):
    escaped = re.escape(theorem)
    if re.search(r"'" + escaped + r"' does not depend on any axioms", output):
        return []
    matches = re.findall(r"'" + escaped + r"' depends on axioms:\s*\[([^]]*)\]", output)
    if len(matches) != 1:
        raise ValueError(f"missing or ambiguous axiom audit for {theorem}")
    axioms = [x.strip() for x in matches[0].split(",") if x.strip()]
    allowed = {"propext", "Classical.choice", "Quot.sound"}
    if set(axioms) - allowed:
        raise ValueError(f"undeclared axiom in {theorem}: {set(axioms) - allowed}")
    return axioms


def reference(args):
    manifest_path = args.manifest or args.out / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    verify_manifest(manifest)
    version = subprocess.check_output(["lean", "--version"], text=True).strip()
    if not re.search(r"version 4\.35\.0(?:\D|$)", version):
        raise ValueError(f"expected Lean 4.35.0, got {version}")
    out = args.out.resolve()
    bridge = out / "reference/torchlean-adapter.py"
    bridge.parent.mkdir(parents=True, exist_ok=True)
    runs = [require_run(["lake", "env", "lean", "--run", "scripts/EmitAdapter.lean", str(bridge)],
                        out / "reference/emit.log")]
    runs.append(require_run([str(Path(manifest["python_environment"]) / "bin/python3"),
                            "scripts/import_reference.py", "--manifest", str(manifest_path.resolve()),
                            "--adapter-script", str(bridge), "--out", str(out / "reference")],
                           out / "reference/capture.log"))
    probe = execute(["lake", "env", "lean", "--run", "scripts/ProbeUpstream.lean",
                     str(out / "reference/reference.json"), str(out / "reference/word-controls.json")],
                    out / "reference/upstream.log")
    if probe["status"] != "failed" or "no arithmetic implementation for int32" not in Path(probe["log"]["path"]).read_text():
        raise ValueError("upstream behavior differs from the diagnosed integer semantic gap; inspect upstream.log")
    runs.append(probe)
    runs.append(require_run(["lake", "build", "Task2.Source", "Task2.Hardware"], out / "reference/proof.log"))
    runs.append(require_run(["lake", "env", "lean", "--run", "Task2/ReferenceControls.lean",
                            str(out / "reference/reference.json"), str(out / "reference/word-controls.json")],
                           out / "reference/controls.log"))
    audit = (out / "reference/controls.log").read_text()
    axioms = audit_axioms(audit, "Task2.source_agrees")
    bound = {k: v for k, v in manifest["artifacts"].items()}
    for name, path in [("reference_graph", out / "reference/reference.json"),
                       ("imported_source", out / "generated/Task2/Imported/Source.lean"),
                       ("source_semantics", ROOT / "Task2/Source.lean"),
                       ("word_semantics", ROOT / "Task2/WordDot.lean"),
                       ("word_controls", out / "reference/word-controls.json"),
                       ("capture_importer", ROOT / "scripts/import_reference.py"),
                       ("capture_bridge", bridge),
                       ("lake_manifest", ROOT / "lake-manifest.json")]:
        bound[name] = artifact(path)
    result = {"status": "proved", "claim": "Task2.source_agrees for every pair of Words",
              "scope": "source semantics only; no RTL equivalence or completion claim",
              "lean_version": version, "axioms": axioms, "runs": runs, "artifacts": bound,
              "hardware_manifest_attached": manifest_path.name == "manifest.json",
              "trust_boundary": json.loads((ROOT / "contract.json").read_text())["trust_boundary"]}
    return result


def hardware(args):
    from import_hardware import import_design
    manifest = json.loads((args.out / "manifest.json").read_text())
    verify_manifest(manifest)
    return import_design(manifest, args.out, args.design, args.yosys)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="stage", required=True)
    p = subs.add_parser("attach")
    p.add_argument("--task2", type=Path, default=Path("/home/roland/LLM2FPGA"))
    p.add_argument("--out", type=Path, default=ROOT / "build")
    p = subs.add_parser("reference")
    p.add_argument("--out", type=Path, default=ROOT / "build")
    p.add_argument("--manifest", type=Path, help="explicit source-only provenance while hardware realization is pending")
    p = subs.add_parser("hardware")
    p.add_argument("--out", type=Path, default=ROOT / "build")
    p.add_argument("--design", choices=["baseline", "candidate"], default="baseline")
    p.add_argument("--yosys", default="yosys")
    args = parser.parse_args()
    started = time.monotonic()
    try:
        result = {"attach": attach, "reference": reference, "hardware": hardware}[args.stage](args)
        result["elapsed_seconds"] = time.monotonic() - started
        key = args.stage + ("-" + args.design if hasattr(args, "design") else "")
        write_json(args.out / (key + "-result.json"), result)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, subprocess.SubprocessError, NotImplementedError) as error:
        result = {"status": "unsupported" if isinstance(error, NotImplementedError) else "failed", "error": str(error), "elapsed_seconds": time.monotonic() - started}
        key = args.stage + ("-" + args.design if hasattr(args, "design") else "")
        write_json(args.out / (key + "-result.json"), result)
        print(json.dumps(result), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
