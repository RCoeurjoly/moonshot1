#!/usr/bin/env python3
"""Check a new universal transition bridge for the actual Sparkle import."""
import concurrent.futures
import json
import os
from pathlib import Path
import re
import subprocess
import time

from run import file_identity, verify_identity

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
LEAN_BIN = Path(os.environ.get("SPARKLE_PROOF_LEAN_BIN",
    "/nix/store/wzr0jh4q335z1d4rcdq0xw9i26ahxvg3-lean-4.35.0/bin"))


# Coordinates in the retained reference model, not native RTL semantics.
STATE_FIELDS = 453
SCALAR_REGISTERS = 451
OUTPUT_FIELDS = 5
OUTPUT_WORD_FIELD = 380
FIELD_BATCH_SIZE = 16
PROOF_WORKERS = 4


def bindings():
    # This supplies a proposed change of coordinates, never a proof verdict.
    old = json.loads((REPO / "build/hardware/baseline/cycle-ir.json").read_text())
    model = json.loads((ROOT / "build/native/Task2RTL.json").read_text())
    registers = {r["name"]: r for r in model["registers"]}
    states = []
    for index, state in enumerate(old["states"]):
        if state["sort"]["kind"] == "memory":
            continue
        if index == OUTPUT_WORD_FIELD:
            wire = "handshake_memory2__handshake_memory_3_0_"
        else:
            wire = re.sub(r"[^A-Za-z0-9_]", "_", state["name"].removeprefix("$driver$"))
        if wire not in registers or registers[wire]["width"] != state["sort"]["width"]:
            raise ValueError(f"state correspondence missing: {wire}")
        states.append({"index": index, "wire": wire, "width": state["sort"]["width"]})
    if len(states) != SCALAR_REGISTERS or len(states) != len(registers) or \
            len({x["wire"] for x in states}) != len(registers):
        raise ValueError("state correspondence is not bijective")
    result = {"inputs": old["inputs"], "states": states, "outputs": old["outputs"]}
    (ROOT / "build/bindings.json").write_text(json.dumps(result, indent=2) + "\n")


def verify_native_artifacts(controls):
    """Bind both the executable model and its register schema to fresh controls."""
    for name in ("Task2RTL.lean", "Task2RTL.json"):
        expected = (ROOT / "build/native" / name).resolve()
        matches = [identity for identity in controls["artifacts"]
                   if Path(identity["path"]).resolve() == expected]
        if len(matches) != 1:
            raise ValueError(f"missing or duplicate native artifact identity: {name}")
        verify_identity(matches[0])


def environment():
    env = dict(os.environ)
    env["PATH"] = str(LEAN_BIN) + ":" + env["PATH"]
    path = subprocess.check_output([str(LEAN_BIN / "lake"), "env", "printenv", "LEAN_PATH"],
                                   cwd=REPO, env=env, text=True).strip()
    env["LEAN_PATH"] = str(ROOT / "Proof/build") + ":" + ":".join(
        str((REPO / part).resolve()) for part in path.split(":"))
    env["LEAN_NUM_THREADS"] = "2"
    return env


def check(module, env):
    output = ROOT / "Proof/build"
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with (output / f"{module}.log").open("w") as stream:
        source = ROOT / f"Proof/{module}.lean"
        if not source.exists():
            source = ROOT / f"Proof/build/generated/{module}.lean"
        result = subprocess.run([str(LEAN_BIN / "lean"), "--root=" + str(source.parent),
                                 "-o", str(output / f"{module}.olean"),
                                 str(source)],
                                cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=600)
    if result.returncode:
        raise RuntimeError((output / f"{module}.log").read_text()[-6000:])
    print(f"PROOF_CHECKED {module}", flush=True)
    log = output / f"{module}.log"
    axioms = {}
    for theorem, names in re.findall(r"'([^']+)' depends on axioms:\s*\[([^\]]*)\]", log.read_text()):
        values = [name.strip() for name in names.split(",") if name.strip()]
        if not set(values) <= {"propext", "Classical.choice", "Quot.sound"}:
            raise ValueError(f"unexpected proof axioms in {theorem}: {values}")
        axioms[theorem] = values
    return {"module": module, "seconds": round(time.monotonic() - started, 6),
            "source": file_identity(source), "object": file_identity(output / f"{module}.olean"),
            "log": file_identity(log), "axioms": axioms}


def generate_fields():
    dest = ROOT / "Proof/build/generated"
    dest.mkdir(parents=True, exist_ok=True)
    fields = [(f"s{i}", f"nextState.g{i//128}.s{i}") for i in range(STATE_FIELDS)]
    fields += [(f"o{i}", f"outputs.o{i}") for i in range(OUTPUT_FIELDS)]
    names = []
    for start in range(0, len(fields), FIELD_BATCH_SIZE):
        name = f"Fields{start//FIELD_BATCH_SIZE}"
        names.append(name)
        source = ["import Helpers", "set_option maxRecDepth 65536",
                  "set_option maxHeartbeats 0", "set_option linter.unusedSimpArgs false",
                  "namespace SparkleProof"]
        if start <= OUTPUT_WORD_FIELD < start + FIELD_BATCH_SIZE:
            source.insert(1, "import OutputWord")
        for field, projection in fields[start:start+FIELD_BATCH_SIZE]:
            if field == "s380":
                source.append("#print axioms agrees_s380")
                continue
            proof = "rfl" if field in ("s30", "s31") else "close_transition"
            source.append(f"theorem agrees_{field} (inputs : Task2.Imported.BaselineCore.Inputs)\n"
                          f"    (state : Task2.Imported.BaselineCore.State) :\n"
                          f"    (evaluate inputs state).{projection} =\n"
                          f"    (Task2.Imported.BaselineCore.evaluate inputs state).{projection} := by\n"
                          f"  {proof}\n#print axioms agrees_{field}")
        source.append("end SparkleProof")
        (dest / f"{name}.lean").write_text("\n\n".join(source) + "\n")
    return names


def generate_assembly(modules):
    core = "Task2.Imported.BaselineCore"
    source = [*(f"import {name}" for name in modules), "import Task2.ProofTools",
              "set_option maxRecDepth 65536", "set_option maxHeartbeats 0",
              "namespace SparkleProof"]

    def ext(name, ty, fields):
        statement = [f"private theorem {name} {{a b : {core}.{ty}}}"]
        statement += [f"    (h{k} : a.{field} = b.{field})" for k, field in enumerate(fields)]
        statement += ["    : a = b := by", "  cases a", "  cases b"]
        statement += [f"  cases h{k}" for k in range(len(fields))]
        statement += ["  rfl"]
        source.append("\n".join(statement))

    for group in range(4):
        ext(f"group{group}_ext", f"StateGroup{group}",
            [f"s{i}" for i in range(group*128, min(STATE_FIELDS, (group+1)*128))])
    ext("state_ext", "State", [f"g{i}" for i in range(4)])
    ext("outputs_ext", "Outputs", [f"o{i}" for i in range(OUTPUT_FIELDS)])
    ext("evaluation_ext", "Evaluation", ["outputs", "nextState", "outputDefined", "transitionDefined"])
    source += [f"theorem transfer_agrees (inputs : {core}.Inputs) (state : {core}.State) :\n"
               f"    evaluate inputs state = {core}.evaluate inputs state := by",
               "  apply evaluation_ext", "  · apply outputs_ext"]
    source += [f"    · exact agrees_o{i} inputs state" for i in range(OUTPUT_FIELDS)]
    source += ["  · apply state_ext"]
    for group in range(4):
        source += [f"    · apply group{group}_ext"]
        source += [f"      · exact agrees_s{i} inputs state"
                   for i in range(group*128, min(STATE_FIELDS, (group+1)*128))]
    source += ["  · rfl", "  · rfl", "#print axioms transfer_agrees", "end SparkleProof"]
    (ROOT / "Proof/build/generated/Assemble.lean").write_text("\n\n".join(source) + "\n")


def reject_mutation(env):
    original = (ROOT / "build/native/Task2RTL.lean").read_text()
    mutated, count = re.subn(r"(?m)^(    «in2_st0» := )(.+)$",
                             r"\1(\2) ^^^ (1 : BitVec 32)", original)
    if count != 1:
        raise ValueError("expected exactly one native output to mutate")
    artifact = ROOT / "build/native/MutatedTask2RTL.lean"
    artifact.write_text(mutated)
    source = (ROOT / "Proof/Main.lean").read_text()
    source = source.replace('"build/native/Task2RTL.lean"', '"build/native/MutatedTask2RTL.lean"')
    source = source.replace("SparkleProof.Main", "SparkleProof.Mutation")
    source = re.sub(r"\bchecked\b", "mutated", source)
    (ROOT / "Proof/build/generated/Mutation.lean").write_text(source)
    try:
        check("Mutation", env)
    except RuntimeError:
        log = ROOT / "Proof/build/Mutation.log"
        text = log.read_text()
        if "artifact_checked" not in text or "error" not in text:
            raise ValueError("mutation failed for a reason other than the artifact proof")
        print("PROOF_MUTATION_REJECTED: imported output XOR 1", flush=True)
        return {"artifact": file_identity(artifact), "log": file_identity(log)}
    raise ValueError("a changed Sparkle output inherited an earlier proof")


def main():
    result_path = ROOT / "build/universal-result.json"
    result_path.unlink(missing_ok=True)
    controls = json.loads((ROOT / "build/result.json").read_text())
    if controls["status"] != "passed_controls" or len(controls["cases"]) != 7:
        raise ValueError("run fresh Sparkle/RTL controls before the universal proof")
    for identity in controls["inputs"]:
        verify_identity(identity)
    verify_native_artifacts(controls)
    bindings()
    env = environment()
    version = subprocess.check_output([str(LEAN_BIN / "lean"), "--version"], text=True).strip()
    if not version.startswith("Lean (version 4.35.0,"):
        raise ValueError(f"the retained proof library requires Lean 4.35.0: {version}")
    reference_log = ROOT / "Proof/build/retained-reference.log"
    reference_log.parent.mkdir(parents=True, exist_ok=True)
    with reference_log.open("w") as stream:
        subprocess.run([str(LEAN_BIN / "lake"), "-q", "build", "Task2.Baseline"],
                       cwd=REPO, env=env, check=True, stdout=stream, stderr=subprocess.STDOUT)
    print("[proof 1/4] Retained reference library checked; checking the native model and proof lemmas", flush=True)
    records = []
    for module in ["NativeArtifact", "ReferenceAdapter", "Model", "Memory", "WordWrites", "WordWritesMaskRight", "Helpers", "OutputWord"]:
        records.append(check(module, env))
    print("[proof 2/4] Checking 453 next-state and 5 output obligations", flush=True)
    modules = generate_fields()
    generate_assembly(modules)
    with concurrent.futures.ThreadPoolExecutor(max_workers=PROOF_WORKERS) as pool:
        pending = {pool.submit(check, module, env): module for module in modules}
        for future in concurrent.futures.as_completed(pending):
            records.append(future.result())
    if sum(len(r["axioms"]) for r in records if r["module"].startswith("Fields")) != STATE_FIELDS + OUTPUT_FIELDS:
        raise ValueError("not all 458 transition field proofs were audited")
    print("[proof 3/4] Composing full transition equality and the universal temporal theorem", flush=True)
    for module in ["Assemble", "Equivalence", "Main"]:
        records.append(check(module, env))
    public = records[-1]["axioms"]
    if "SparkleProof.Main.observable_equivalence" not in public or "SparkleProof.Main.first_result" not in public:
        raise ValueError("missing public theorem axiom audit")
    print("[proof 4/4] Rejecting a mutation of the native output", flush=True)
    mutation = reject_mutation(env)
    sources = [file_identity(p) for p in sorted((ROOT / "Proof").glob("*.lean"))]
    sources += [file_identity(ROOT / "prove.py"), file_identity(ROOT / "build/native/Task2RTL.lean"),
                file_identity(ROOT / "build/bindings.json"), file_identity(ROOT / "build/result.json"),
                file_identity(REPO / "build/hardware/baseline/cycle-ir.json")]
    result = {"status": "proved", "universal_equivalence_proved": True,
              "public_theorem": "SparkleProof.Main.observable_equivalence",
              "first_result_theorem": "SparkleProof.Main.first_result",
              "completion_edges": 436, "state_fields_checked": STATE_FIELDS, "outputs_checked": OUTPUT_FIELDS,
              "axioms": public, "lean": version,
              "model_semantics": "upstream Tools.SVParser.VerifyEmit.denote",
              "native_model": file_identity(ROOT / "build/native/Task2RTL.lean"), "controls": file_identity(ROOT / "build/result.json"),
              "mutation_rejected": mutation, "inputs": sources,
              "retained_reference_check": file_identity(reference_log), "checks": records,
              "proof_reuse": "The unchanged temporal theorem is composed only after the new complete transition equivalence proof.",
              "trust_boundaries": ["Slang/Yosys elaboration and normalization", "input-memory lift",
                                   "Sparkle SV parser/lowering and upstream VerifyEmit.denote",
                                   "native-source declaration layout and record coordinate adapter"]}
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"SPARKLE_UNIVERSAL_EQUIVALENCE_PROVED: {result_path}")


if __name__ == "__main__":
    main()
