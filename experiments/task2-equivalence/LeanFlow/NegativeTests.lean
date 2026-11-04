import LeanFlow.Graph
import LeanFlow.SMT
import LeanFlow.Bridge

open LeanFlow

private def rejectProof (name source : String) : IO Unit := do
  let file := s!"build/lean-flow/negative-{name}.lean"
  IO.FS.writeFile file source
  let result ← IO.Process.output {cmd := "lean", args := #[file]}
  IO.FS.writeFile s!"build/lean-flow/negative-{name}.log" (result.stdout ++ result.stderr)
  unless result.exitCode != 0 && (result.stdout ++ result.stderr).contains "error" do
    throw (IO.userError s!"invalid {name} proof was accepted")

def main : IO Unit := do
  let mainSource ← IO.FS.readFile "LeanFlow/Main.lean"
  let json ← IO.ofExcept (Lean.Json.parse (← IO.FS.readFile "build/lean-flow/pytorch.json"))
  let nodes ← IO.ofExcept ((← IO.ofExcept (json.getObjVal? "nodes")).getArr?)
  let mutant := json.setObjVal! "nodes" (.arr (nodes.set! 2
    (nodes[2]!.setObjVal! "parents" (Lean.toJson (#[0,0] : Array Nat)))))
  let mutantGraph ← IO.ofExcept (Graph.parse mutant.compress)
  let changed ← IO.ofExcept (Graph.scalar mutantGraph (fun _ => 1) (fun _ => 2))
  unless changed == 16 do throw (IO.userError "graph mutation did not change the dot-product result from 32 to 16")
  IO.FS.writeFile "build/lean-flow/mutant-graph.json" mutant.compress
  rejectProof "graph" (mainSource.replace "build/lean-flow/pytorch.json" "build/lean-flow/mutant-graph.json")
  let text ← IO.FS.readFile "build/lean-flow/accelerator.smt2"
  let mutant := text.replace "(bvor " "(bvand "
  unless mutant != text do throw (IO.userError "SMT mutation made no change")
  let mutantProgram ← IO.ofExcept (SMT.parse mutant)
  let inputs : Bridge.CoreInputs := {i0 := 0,i1 := 0,i2 := 0,i3 := 0,i4 := 0,i5 := 0}
  let state := Bridge.testState 1
  let changed ← IO.ofExcept (SMT.eval mutantProgram (Bridge.encodeInputs inputs) (Bridge.encodeState state))
  let changedWord ← IO.ofExcept (SMT.bitsAt 64 changed.nextState 0)
  unless changedWord != (Task2.Imported.BaselineCore.evaluate inputs state).nextState.g0.s0 do
    throw (IO.userError "SMT mutation has no demonstrated state counterexample")
  IO.FS.writeFile "build/lean-flow/mutant-hardware.smt2" mutant
  rejectProof "hardware" (mainSource.replace "build/lean-flow/accelerator.smt2" "build/lean-flow/mutant-hardware.smt2")
  rejectProof "false" "import Task2.ProofTools\nexample : (1 : Nat) = 2 := by kernel_rfl\n"
  IO.println "LEAN_NEGATIVE_TESTS passed: well-typed changed graph/SMT and false proof rejected"
