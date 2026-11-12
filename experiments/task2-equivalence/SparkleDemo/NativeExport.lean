import Tools.SVParser
import Tools.SVParser.Verify
import Tools.SVParser.VerifyEmit
import Sparkle.Backend.CSim

/-! Export a readable state machine using Sparkle's own expression reflector.
    This module arranges records and preserves wire sharing. Operator semantics
    are supplied exclusively by `Tools.SVParser.VerifyEmit.denote`. -/
namespace NativeExport

open Lean Elab Command Sparkle.IR.AST
open Tools.SVParser.VerifyEmit

private abbrev References := Std.HashMap String Syntax

-- The pinned runtime crashes on a 128-field constructor. Inherited projections
-- retain named register access while keeping each storage constructor small.
private def stateGroupSize : Nat := 64

private def parseTerm (source : String) : CommandElabM Syntax := do
  match Parser.runParserCategory (← getEnv) `term source with
  | .ok term => pure term
  | .error message => throwError "{message}"

private def parseCommand (source : String) : CommandElabM Syntax := do
  match Parser.runParserCategory (← getEnv) `command source with
  | .ok command => pure command
  | .error message => throwError "{message}"

-- Quotation hygiene is useful during elaboration, but portable generated
-- source must refer to public Std names rather than macro-scoped identifiers.
private partial def portable : Syntax → Syntax
  | .ident info raw name _ => .ident info raw name.eraseMacroScopes []
  | .node info kind args => .node info kind (args.map portable)
  | stx => stx

private def reflect (widths : Std.HashMap String Nat) (refs : References)
    (expected : Nat) (expression : Sparkle.IR.AST.Expr) : CommandElabM String := do
  let actual ← IO.ofExcept (widthOf widths expression)
  unless actual == expected do
    throwError "native Sparkle width mismatch: expected {expected}, got {actual}"
  let term ← denote widths expression
  let term ← term.raw.replaceM fun stx => do
    if stx.isIdent then
      return refs[stx.getId.eraseMacroScopes.toString]?
    return none
  return (← liftCoreM (PrettyPrinter.ppTerm ⟨portable term⟩)).pretty 110

private def field (name : String) : String := s!"«{name}»"

private def record (name : String) (fields : List (String × Nat)) : String :=
  s!"structure {name} where\n" ++ String.intercalate "\n"
    (fields.map fun (name, width) => s!"  {field name} : BitVec {width}")

private def recordValue (fields : List (String × String)) : String :=
  "  {\n" ++ String.intercalate "\n"
    (fields.map fun (name, value) => s!"    {field name} := {value}") ++ "\n  }"

private def addReference (refs : References) (name value : String) : CommandElabM References := do
  let key := (varIdent name).getId.toString
  return refs.insert key (← parseTerm value)

private def generate (m : Sparkle.IR.AST.Module) : CommandElabM (Array String × Json) := do
  let widths := widthTable m
  let model := Tools.SVParser.Verify.extractModel m
  let logicalNames := (m.inputs ++ m.outputs ++ m.wires).map (·.name) |>.eraseDups
  let reflectedNames := logicalNames.map fun name => (varIdent name).getId.toString
  unless reflectedNames.eraseDups.length == reflectedNames.length do
    throwError "RTL names collide after Sparkle identifier sanitization"
  for name in logicalNames do
    let some width := widths[name]? | throwError "missing width for {name}"
    unless width > 0 && width ≤ 64 do throwError "unsupported scalar width {width}: {name}"
  let filtered := m.body.filter fun statement => match statement with
    | .assign lhs (.ref rhs) => lhs != rhs
    | _ => true
  let (ordered, hasCycle) := Sparkle.Backend.CSim.scheduleEvalBody none m filtered
  if hasCycle then throwError "combinational cycle in imported Sparkle IR"
  for statement in ordered do
    match statement with
    | .assign .. => pure ()
    | .register name clock _ _ _ =>
      unless clock == "clock" do throwError "unsupported clock {clock} on {name}"
    | _ => throwError "expected flattened scalar assignments and registers"
  for register in model.registers do
    unless widths[register.name]? == some register.width do
      throwError "Sparkle register width does not match its declaration: {register.name}"

  let inputFields := m.inputs.map fun port => (port.name, port.ty.bitWidth)
  let stateFields := model.registers.map fun register => (register.name, register.width)
  let outputFields := m.outputs.map fun port => (port.name, port.ty.bitWidth)
  let mut commands := #[record "Inputs" inputFields]
  if stateFields.length > stateGroupSize then
    let mut parents := []
    for group in [: (stateFields.length + stateGroupSize - 1) / stateGroupSize] do
      let name := s!"StateGroup{group}"
      commands := commands.push (record name
        (stateFields.drop (group*stateGroupSize) |>.take stateGroupSize))
      parents := parents ++ [name]
    commands := commands.push ("structure State extends " ++ String.intercalate ", " parents ++ " where")
  else
    commands := commands.push (record "State" stateFields)
  commands := commands ++ #[record "Outputs" outputFields,
    "structure Evaluation where\n  outputs : Outputs\n  nextState : State"]
  let parameters := "(inputs : Inputs) (state : State)"
  let mut refs : References := {}
  for (name, _) in inputFields do
    refs ← addReference refs name s!"inputs.{field name}"
  for (name, _) in stateFields do
    refs ← addReference refs name s!"state.{field name}"

  let mut wireIndex := 0
  for statement in ordered do
    if let .assign name expression := statement then
      let some width := widths[name]? | throwError "missing wire width: {name}"
      let value ← reflect widths refs width expression
      commands := commands.push s!"-- RTL wire `{name}`.\n@[noinline] def wire{wireIndex} {parameters} : BitVec {width} :=\n  {value}"
      refs ← addReference refs name s!"(wire{wireIndex} inputs state)"
      wireIndex := wireIndex + 1

  let mut nextFields : List (String × String) := []
  for (register, index) in model.registers.zipIdx do
    let value ← reflect widths refs register.width register.nextExpr
    commands := commands.push s!"-- Next value of `{register.name}`.\n@[noinline] def next{index} {parameters} : BitVec {register.width} :=\n  {value}"
    nextFields := nextFields ++ [(register.name, s!"next{index} inputs state")]
  commands := commands.push (s!"def nextState {parameters} : State :=\n" ++ recordValue nextFields)
  let mut outputs : List (String × String) := []
  for port in m.outputs do
    let value ← reflect widths refs port.ty.bitWidth (.ref port.name)
    outputs := outputs ++ [(port.name, value)]
  commands := commands.push (s!"def outputs {parameters} : Outputs :=\n" ++ recordValue outputs)
  commands := commands.push (s!"def evaluate {parameters} : Evaluation :=\n" ++
    "  { outputs := outputs inputs state, nextState := nextState inputs state }")
  let mut initialFields : List (String × String) := []
  for register in model.registers do
    let value ← reflect widths {} register.width (.const register.initValue register.width)
    initialFields := initialFields ++ [(register.name, value)]
  commands := commands.push ("-- Concrete simulation seed; universal proofs quantify over arbitrary state.\n" ++
    "def initialState : State :=\n" ++ recordValue initialFields)
  let metadata := Json.mkObj [
    ("semantics", toJson "Tools.SVParser.VerifyEmit.denote"),
    ("inputs", toJson inputFields), ("outputs", toJson outputFields),
    ("registers", toJson (model.registers.map fun register => Json.mkObj [
      ("name", toJson register.name), ("width", toJson register.width)])),
    ("wire_count", toJson wireIndex)]
  return (commands, metadata)

elab "export_native_sparkle " source:str " as " target:ident " into " directory:str : command => do
  let design ← IO.ofExcept (Tools.SVParser.Lower.parseAndLowerHierarchical
    (← IO.FS.readFile source.getString))
  unless design.modules.length == 1 do throwError "expected one flattened RTL module"
  let some hardwareModule := design.modules.head? | throwError "empty Sparkle design"
  let (commands, metadata) ← generate hardwareModule
  let options := #["set_option maxRecDepth 65536", "set_option maxHeartbeats 0",
    "set_option linter.unusedVariables false"]
  let name := target.getId.toString
  let text := "import Std\n\nnamespace " ++ name ++ "\n\n" ++
    String.intercalate "\n" options.toList ++ "\n\n" ++
    String.intercalate "\n\n" commands.toList ++ "\n\nend " ++ name ++ "\n"
  let out := System.FilePath.mk directory.getString
  IO.FS.createDirAll out
  IO.FS.writeFile (out / s!"{name}.lean") text
  IO.FS.writeFile (out / s!"{name}.json") metadata.pretty
  elabCommand (← `(command| namespace $target))
  for option in options do elabCommand (← parseCommand option)
  for command in commands do elabCommand (← parseCommand command)
  elabCommand (← `(command| end $target))
  logInfo m!"Native Sparkle model: {hardwareModule.name}, {commands.size} declarations"

end NativeExport
