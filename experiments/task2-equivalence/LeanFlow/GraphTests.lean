import LeanFlow.Graph

open LeanFlow

private def check (condition : Bool) (message : String) : IO Unit :=
  unless condition do throw (IO.userError message)

private def failed {α : Type} : Except String α → Bool
  | .error _ => true
  | .ok _ => false

def main : IO Unit := do
  let text ← IO.FS.readFile "build/lean-flow/pytorch.json"
  let graph ← IO.ofExcept (Graph.parse text)
  let one : Graph.Tensor := ⟨[16], Array.replicate 16 (1#32)⟩
  let two : Graph.Tensor := ⟨[16], Array.replicate 16 (2#32)⟩
  let output ← IO.ofExcept (Graph.eval graph #[one, two])
  check (output == #[⟨[], #[32#32]⟩]) "imported matmul did not compute 32"
  let negative : Graph.Tensor := ⟨[16], #[(4294967295#32)] ++ Array.replicate 15 0⟩
  let output ← IO.ofExcept (Graph.eval graph #[negative, two])
  check (output == #[⟨[], #[4294967294#32]⟩]) "signed word/overflow semantics lost"
  check (failed (Graph.eval graph #[⟨[16], #[1#32]⟩, two])) "invalid tensor length accepted"
  let json ← IO.ofExcept (Lean.Json.parse text)
  check (failed (Graph.parse (json.setObjVal! "capture_constraints" (.arr #[.str "extra"])).compress))
    "uninterpreted capture constraints accepted"
  check (failed (Graph.parse (text.replace "\"matmul\"" "\"not_an_operator\""))) "unsupported operator accepted"
  check (failed (Graph.parse (text.replace "\"width\": 32" "\"width\": 64"))) "unsupported integer width accepted"
  let composed : Graph.Program :=
    { nodes := #[⟨.input, #[], [16]⟩, ⟨.input, #[], [16]⟩,
                 ⟨.add, #[0,1], [16]⟩, ⟨.matmul, #[2,1], []⟩],
      inputs := #[0,1], outputs := #[3] }
  let output ← IO.ofExcept (Graph.eval composed #[one,two])
  check (output == #[⟨[], #[96#32]⟩]) "node interpreter ignored composed add/matmul graph"
  IO.println "LEAN_GRAPH_TESTS passed: real JSON, node execution, overflow, rejection, composition"
