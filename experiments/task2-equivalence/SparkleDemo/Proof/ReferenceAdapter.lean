import NativeArtifact
import Task2.Imported.BaselineCore

/-! A change of record coordinates for the retained reference proof.
    This adapter only copies ports/registers and reads the two input memories.
    All circuit expressions remain in the native Sparkle model. -/
open Lean Elab Command
namespace SparkleProof

private def field (name : String) := s!"«{name}»"
private def stateField (index : Nat) := s!"g{index / 128}.s{index}"
private def recordValue (fields : Array String) :=
  "{ " ++ String.intercalate ", " fields.toList ++ " }"

private def generate (bindings : Json) (name : String) : Except String (Array String) := do
  let core := "Task2.Imported.BaselineCore"
  let params := s!"(inputs : {core}.Inputs) (state : {core}.State)"
  let mut inputs : Array String := #[]
  for binding in ← bindings.getObjValAs? (Array Json) "inputs" do
    let port ← binding.getObjValAs? String "name"
    let coordinate ← binding.getObjValAs? String "field"
    inputs := inputs.push s!"{field port} := inputs.{coordinate}"
  for (label, index) in [("a", 30), ("b", 31)] do
    for address in [:16] do
      inputs := inputs.push s!"ram_{label}_{address} := state.{stateField index} ({address}#4)"
  let states ← bindings.getObjValAs? (Array Json) "states"
  unless states.size == 451 do throw "expected all 451 native scalar registers"
  let mut state := #[]
  let mut next : Std.HashMap Nat String := {}
  for binding in states do
    let wire ← binding.getObjValAs? String "wire"
    let index ← binding.getObjValAs? Nat "index"
    state := state.push s!"{field wire} := state.{stateField index}"
    next := next.insert index s!"native.{field wire}"
  next := next.insert 30 "state.g0.s30" |>.insert 31 "state.g0.s31"
  unless next.size == 453 do throw "incomplete reference state coordinates"
  let mut groups := #[]
  for group in [:4] do
    let mut fields := #[]
    for index in [group*128:min 453 ((group+1)*128)] do
      let some value := next[index]? | throw s!"missing reference state {index}"
      fields := fields.push s!"s{index} := {value}"
    groups := groups.push s!"g{group} := {recordValue fields}"
  let mut outputs := #[]
  for binding in ← bindings.getObjValAs? (Array Json) "outputs" do
    let port ← binding.getObjValAs? String "name"
    let coordinate ← binding.getObjValAs? String "field"
    outputs := outputs.push s!"{coordinate} := native.{field port}"
  return #[
    s!"def {name}_inputs {params} : RTL.Inputs := {recordValue inputs}",
    s!"def {name}_state (state : {core}.State) : RTL.State := {recordValue state}",
    s!"def {name}_next (state : {core}.State) (native : RTL.State) : {core}.State := {recordValue groups}",
    s!"def {name}_outputs (native : RTL.Outputs) : {core}.Outputs := {recordValue outputs}",
    s!"def {name} {params} : {core}.Evaluation :=\n" ++
      s!"  let native := RTL.evaluate ({name}_inputs inputs state) ({name}_state state)\n" ++
      s!"  \{ outputs := {name}_outputs native.outputs, nextState := {name}_next state native.nextState," ++
      " outputDefined := true, transitionDefined := true }"]

elab "adapt_native_reference " path:str " as " name:ident : command => do
  let bindings ← IO.ofExcept (Json.parse (← IO.FS.readFile path.getString))
  let sources ← IO.ofExcept (generate bindings name.getId.toString)
  for source in sources do
    let command ← match Parser.runParserCategory (← getEnv) `command source with
      | .ok stx => pure stx
      | .error message => throwError "{message}"
    elabCommand command

end SparkleProof
