import Lean

open Lean

private def command (cmd : String) (args : Array String) : IO String := do
  let result ← IO.Process.output {cmd,args}
  unless result.exitCode == 0 do throw (IO.userError s!"{cmd}: {result.stderr}")
  pure result.stdout

private def writeIfChanged (path : System.FilePath) (contents : String) : IO Unit := do
  if ← path.pathExists then
    if (← IO.FS.readFile path) == contents then return
  IO.FS.createDirAll path.parent.get!
  IO.FS.writeFile path contents

/-- Restore immutable, retained proof sources, not generated semantics. Lake
    checks these sources with their dependencies before using their theorems. -/
def main : IO Unit := do
  let destination : System.FilePath := "build/lean-flow"
  IO.FS.createDirAll (destination / "archive")
  let _ ← command "tar" #["-xzf", "reports/baseline-proof/checked-inputs.tar.gz",
    "-C", (destination / "archive").toString]
  let metadata ← IO.ofExcept (Json.parse (← IO.FS.readFile "reports/baseline-proof/result.json"))
  let artifacts ← IO.ofExcept (metadata.getObjVal? "artifacts")
  let restore (key : String) (target : System.FilePath) : IO Unit := do
    let entry ← IO.ofExcept (artifacts.getObjVal? key)
    let oldPath ← IO.ofExcept (entry.getObjValAs? String "path")
    let expected ← IO.ofExcept (entry.getObjValAs? String "sha256")
    let source := destination / "archive/artifacts" / (System.FilePath.mk oldPath).fileName.get!
    let actual ← command "sha256sum" #[source.toString]
    unless actual.startsWith (expected ++ " ") do throw (IO.userError s!"retained artifact hash mismatch: {key}")
    writeIfChanged target (← IO.FS.readFile source)
  let root := destination / "retained"
  for name in ["BaselineCore", "BaselineAdapter", "BaselineTrace", "BaselineInitial",
      "BaselineFinalArithmetic", "BaselineTraceCorrect"] do
    let key := if name == "BaselineCore" then "imported_core" else if name == "BaselineAdapter" then "device_adapter"
      else "certificate_" ++ name
    restore key (root / "Task2/Imported" / (name ++ ".lean"))
  for i in [:51] do
    let name := s!"BaselineCuts{i}"
    restore ("certificate_" ++ name) (root / "Task2/Imported" / (name ++ ".lean"))
  for i in [:22] do
    let name := s!"BaselineTransitions{i}"
    restore ("certificate_" ++ name) (root / "Task2/Imported" / (name ++ ".lean"))
  for name in ["Baseline", "Trace", "ProofTools"] do
    restore s!"proof_support_{name}.lean" (root / "Task2" / (name ++ ".lean"))
  restore "imported_source" "build/generated/Task2/Imported/Source.lean"
  restore "native_smt" (destination / "accelerator.smt2")
  IO.println "LEAN_PREPARED retained proof sources and hardware SMT (SHA-256 checked)"
