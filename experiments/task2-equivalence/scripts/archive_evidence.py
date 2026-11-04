"""Retain the exact bytes named by an existing stage result without changing its verdict."""
import argparse
import json
from pathlib import Path
import shutil

from run import digest, verify_manifest


def seal(result, destination):
    verify_manifest(result)
    destination=Path(destination).resolve()
    copied={}

    def visit(value):
        if isinstance(value,list):return [visit(item) for item in value]
        if not isinstance(value,dict):return value
        if "path" in value and "sha256" in value:
            source=Path(value["path"])
            if digest(source)!=value["sha256"]:
                raise ValueError(f"artifact identity changed before archiving: {source}")
            if str(source).startswith("/nix/store/"):
                return dict(value)
            key=str(source),value["sha256"]
            if key not in copied:
                target=destination/"artifacts"/(value["sha256"][:20]+"-"+source.name)
                target.parent.mkdir(parents=True,exist_ok=True)
                if source.is_dir():
                    if not target.exists():shutil.copytree(source,target)
                else:shutil.copyfile(source,target)
                if digest(target)!=value["sha256"]:
                    raise ValueError(f"artifact identity changed while archiving: {source}")
                copied[key]=target
            return {**value,"path":str(copied[key]),"original_path":str(source)}
        return {key:visit(item) for key,item in value.items()}

    sealed=visit(result)
    sealed["archive"]={"scope":"exact checked inputs and logs; verdict unchanged",
                       "directory":str(destination),"retained_artifacts":len(copied)}
    verify_manifest(sealed)
    return sealed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--write-result",type=Path)
    args=parser.parse_args()
    raw=args.result.read_text()
    result=seal(json.loads(raw),args.out)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"unsealed-result.json").write_text(raw)
    target=args.write_result or args.out/"result.json"
    target.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"archive":result["archive"],"result":str(target)}))


if __name__=="__main__":main()
