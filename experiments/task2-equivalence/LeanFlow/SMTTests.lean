import LeanFlow.SMT

open LeanFlow

private def check (condition : Bool) (message : String) : IO Unit :=
  unless condition do throw (IO.userError message)

private def failed {α : Type} : Except String α → Bool
  | .error _ => true
  | _ => false

private def fixture (expression : String) : String := s!"
(declare-datatype main_Inputs ((main_Inputs (main_Inputs_x (_ BitVec 8)))))
(declare-datatype main_Outputs ((main_Outputs (main_Outputs_y (_ BitVec 8)))))
(declare-datatype main_State ((main_State (main_State_s (_ BitVec 8)))))
(declare-datatypes ((Pair 2)) ((par (X Y) ((pair (first X) (second Y))))))
(define-fun main ((inputs main_Inputs) (state main_State)) (Pair main_Outputs main_State)
  (let ((x (main_Inputs_x inputs)))
  (let ((s (main_State_s state)))
  (let ((answer {expression}))
    (pair (main_Outputs answer) (main_State s))))))"

private def execute (expression : String) (x s expected : Nat) : IO Unit := do
  let program ← IO.ofExcept (SMT.parse (fixture expression))
  let result ← IO.ofExcept (SMT.eval program #[.bits 8 (BitVec.ofNat 8 x)] #[.bits 8 (BitVec.ofNat 8 s)])
  let word ← IO.ofExcept (SMT.bitsAt 8 result.outputs 0)
  check (word.toNat == expected) s!"SMT {expression}: got {word.toNat}, expected {expected}"

def main : IO Unit := do
  execute "(bvadd x s)" 255 2 1
  execute "(bvmul x s)" 255 2 254
  execute "(bvor x s)" 1 2 3
  execute "(bvand x s)" 1 2 0
  execute "(bvxor x s)" 3 1 2
  execute "(bvxor x s #b00000011)" 1 2 0
  check (failed (SMT.parse (fixture "(bvxor x)"))) "unary SMT bvxor accepted"
  check (failed (SMT.parse (fixture "(bvxor)"))) "empty SMT bvxor accepted"
  execute "(bvashr x s)" 128 8 255
  execute "(bvlshr x s)" 128 8 0
  execute "(bvshl x s)" 1 255 0
  execute "(bvudiv x #b00000000)" 17 0 255
  execute "(bvurem x #b00000000)" 17 0 17
  execute "(ite (bvsgt x s) #b00000001 #b00000000)" 128 1 0
  execute "(ite (bvugt x s) #b00000001 #b00000000)" 128 1 1
  execute "(concat ((_ extract 3 0) x) ((_ extract 7 4) x))" 18 0 33
  check (failed (SMT.parse (fixture "(bvadd x #b0)"))) "ill-typed SMT accepted"
  check (failed (SMT.parse (fixture "missing"))) "unbound SMT atom accepted"
  check (failed (SMT.parse (fixture "(oracle x)"))) "unsupported SMT operator accepted"
  check (failed (SMT.parse ((fixture "x") ++ "(assert false)"))) "non-initializer assertion silently ignored"
  check (failed (SMT.parse ((fixture "x").replace "(first X)" "(first Y)")))
    "malformed Pair declaration accepted"
  check (failed (SMT.parse ((fixture "x").replace "main_Outputs_y" "main_Inputs_x")))
    "duplicate datatype selector accepted"
  check (failed (SMT.parse ((fixture "x").replace "((s (main_State_s state)))" "((x (main_State_s state)))")))
    "shadowed let binding accepted"
  let memoryText := "
(declare-datatype main_Inputs ((main_Inputs (main_Inputs_x (_ BitVec 8)))))
(declare-datatype main_Outputs ((main_Outputs (main_Outputs_y (_ BitVec 8)))))
(declare-datatype main_State ((main_State (main_State_mem (Array (_ BitVec 2) (_ BitVec 8))))))
(declare-datatypes ((Pair 2)) ((par (X Y) ((pair (first X) (second Y))))))
(define-fun main ((inputs main_Inputs) (state main_State)) (Pair main_Outputs main_State)
  (let ((m (main_State_mem state)))
  (let ((x (main_Inputs_x inputs)))
  (let ((updated (store m #b01 x)))
  (let ((answer (select updated #b01)))
    (pair (main_Outputs answer) (main_State updated)))))))"
  let program ← IO.ofExcept (SMT.parse memoryText)
  let result ← IO.ofExcept (SMT.eval program #[.bits 8 37] #[.memory 2 8 (fun _ => 0)])
  let answer ← IO.ofExcept (SMT.bitsAt 8 result.outputs 0)
  check (answer == 37) "memory select/store failed"
  let actualText ← IO.FS.readFile "build/lean-flow/accelerator.smt2"
  let actual ← IO.ofExcept (SMT.parse actualText)
  check (actual.inputs.size == 6 && actual.states.size == 453 && actual.outputs.size == 5)
    "full Task2 SMT declarations did not parse"
  let finalPair := "(pair (main_Outputs answer) (main_State s))"
  let shadow (name : String) (output := "answer") :=
    (fixture "x").replace finalPair s!"(let (({name} answer)) (pair (main_Outputs {output}) (main_State s)))"
  let actualShadow (name : String) :=
    (actualText.replace "(pair\n" s!"(let (({name} in2_st0)) (pair\n").replace
      "(declare-const main-initial" ")\n(declare-const main-initial"
  let cases := #[
    ("pair constructor shadow", shadow "pair"),
    ("record constructor shadow", shadow "main_Outputs"),
    ("selector shadow", shadow "main_Inputs_x" "(main_Inputs_x inputs)"),
    ("operator shadow", shadow "bvadd" "(bvadd x s)"),
    ("function shadow", shadow "main"),
    ("Pair selector shadow", shadow "first"),
    ("syntax shadow", shadow "let"),
    ("actual pair constructor shadow", actualShadow "pair"),
    ("actual initial constant shadow", actualShadow "main-initial"),
    ("selector/constructor collision", (fixture "x").replace "main_Outputs_y" "main_Inputs"),
    ("function/selector collision", (fixture "x").replace "(define-fun main " "(define-fun main_Inputs_x "),
    ("global operator collision", (fixture "x").replace "main_State_s" "bvadd")]
  let mut accepted := #[]
  for (name,text) in cases do
    if !failed (SMT.parse text) then accepted := accepted.push name
  check accepted.isEmpty s!"SMT invalid namespaces accepted: {String.intercalate ", " accepted.toList}"
  IO.println s!"LEAN_SMT_TESTS passed: primitives, rejection, memories; actual circuit {actual.nodes.size} nodes"
