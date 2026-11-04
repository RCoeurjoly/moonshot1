"""Add opt -full at the shared physical checkpoint; never count a no-op as a result."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess


def number(value):
    return int(value,2) if isinstance(value,str) else int(value)


def structural_summary(module):
    cells=list(module["cells"].values())
    state_bits=sum(number(c["parameters"]["WIDTH"]) for c in cells
                   if c["type"] in ("$dff","$dffe","$sdff","$sdffe","$sdffce","$adff","$adffe"))
    widths=sum(number(v) for c in cells for k,v in c["parameters"].items()
               if k in ("WIDTH","A_WIDTH","B_WIDTH","Y_WIDTH","S_WIDTH"))
    return {"cell_types":dict(sorted(Counter(c["type"] for c in cells).items())),
            "state_bits":state_bits,"cell_width_bits":widths}


def structural_delta(before,after):
    interface=lambda module:{name:(port["direction"],len(port["bits"])) for name,port in module["ports"].items()}
    if interface(before)!=interface(after):raise ValueError("candidate interface changed")
    old,new=structural_summary(before),structural_summary(after)
    return {"status":"no_change" if old==new else "prepared","before":old,"after":new,
            "criterion":"changed cell-type counts or total cell/state widths at the same physical checkpoint"}


def create_variant(out,yosys="yosys"):
    from run import artifact,execute,verify_manifest,write_json
    out=Path(out).resolve()
    manifest=json.loads((out/"manifest.json").read_text());verify_manifest(manifest)
    proof=json.loads((out/"check-baseline-result.json").read_text());verify_manifest(proof)
    if proof["status"]!="proved":raise ValueError("baseline theorem must pass before creating the variant")
    if proof["artifacts"]["baseline"]["sha256"]!=manifest["artifacts"]["baseline"]["sha256"]:
        raise ValueError("baseline proof covers a different artifact identity")
    canonical=Path(proof["artifacts"]["canonical"]["path"])
    folder=out/"hardware/candidate/compiler";folder.mkdir(parents=True,exist_ok=True)
    rtl=out/"hardware/candidate/rtl";rtl.mkdir(parents=True,exist_ok=True)
    before,after=folder/"before.json",folder/"after.json"
    script=folder/"opt-full.ys"
    script.write_text("\n".join([
        "read_rtlil "+json.dumps(str(canonical)),"hierarchy -top main","check",
        "write_json "+json.dumps(str(before)),"opt -full","check",
        "write_rtlil "+json.dumps(str(folder/"candidate.il")),
        "write_json "+json.dumps(str(after)),
        "write_verilog -noattr "+json.dumps(str(rtl/"main.sv")),""] ))
    version=subprocess.check_output([yosys,"-V"],text=True).strip()
    run=execute([yosys,"-s",str(script)],folder/"opt-full.log")
    if run["status"]!="prepared":
        return {"status":run["status"],"scope":"no candidate correctness claim","runs":[run]}
    result=structural_delta(json.loads(before.read_text())["modules"]["main"],
                            json.loads(after.read_text())["modules"]["main"])
    (rtl/"sources.f").write_text(str(rtl/"main.sv")+"\n")
    result.update({"scope":"compiler-produced structural change only; candidate proof still required",
                   "transformation":"opt -full","yosys_version":version,"runs":[run],
                   "artifacts":{"baseline_checkpoint":artifact(canonical),"baseline_proof":artifact(out/"check-baseline-result.json"),
                                "script":artifact(script),"before":artifact(before),"after":artifact(after),
                                "candidate_checkpoint":artifact(folder/"candidate.il"),"candidate":artifact(rtl)}})
    if result["status"]=="prepared":
        manifest["artifacts"]["candidate"]=result["artifacts"]["candidate"]
        write_json(out/"manifest.json",manifest)
    write_json(out/"variant-result.json",result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,default=Path("build"));p.add_argument("--yosys",default="yosys")
    args=p.parse_args();print(json.dumps(create_variant(args.out,args.yosys),indent=2))


if __name__=="__main__":main()
