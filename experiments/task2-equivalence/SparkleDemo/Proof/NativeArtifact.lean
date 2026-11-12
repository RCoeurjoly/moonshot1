import Lean

/-! Load the generated native model into a fresh namespace. Validate its syntax
    before elaboration: only the records, definitions, options and pure terms
    emitted by NativeExport are supported. This is a generated-format validator. -/
open Lean Elab Command

namespace SparkleProof

private partial def sameShape : Syntax → Syntax → Bool
  | .missing, .missing => true
  | .node _ k xs, .node _ k' ys => k == k' && xs.isEqv ys sameShape
  | .atom _ a, .atom _ b => a == b
  | .ident _ _ a _, .ident _ _ b _ => a == b
  | _, _ => false

private def parseCommand (source : String) : CommandElabM Syntax := do
  match Parser.runParserCategory (← getEnv) `command source with
  | .ok stx => pure stx
  | .error message => throwError "{message}"

-- This is a syntax whitelist, not an interpretation of circuit operators.
-- In particular, tactic/do bodies, holes, sorry and quotations are excluded.
private def generatedKinds : List Name := [
  ``Lean.Parser.Command.declId, ``Lean.Parser.Command.declModifiers,
  ``Lean.Parser.Command.declValSimple, ``Lean.Parser.Command.declaration,
  ``Lean.Parser.Command.definition, ``Lean.Parser.Command.extends,
  ``Lean.Parser.Command.optDeclSig, ``Lean.Parser.Command.optDeriving,
  ``Lean.Parser.Command.structFields, ``Lean.Parser.Command.structParent,
  ``Lean.Parser.Command.structSimpleBinder, ``Lean.Parser.Command.structure,
  ``Lean.Parser.Command.structureTk, ``Lean.Parser.Attr.simple,
  ``Lean.Parser.Term.app, ``Lean.Parser.Term.attrInstance,
  ``Lean.Parser.Term.attrKind, ``Lean.Parser.Term.attributes,
  ``Lean.Parser.Term.explicitBinder, ``Lean.Parser.Term.hygienicLParen,
  ``Lean.Parser.Term.optEllipsis, ``Lean.Parser.Term.paren,
  ``Lean.Parser.Term.structInst, ``Lean.Parser.Term.structInstField,
  ``Lean.Parser.Term.structInstFieldDef, ``Lean.Parser.Term.structInstFields,
  ``Lean.Parser.Term.structInstLVal, ``Lean.Parser.Term.typeAscription,
  ``Lean.Parser.Term.typeSpec, ``Lean.Parser.Termination.suffix] ++
  (["hygieneInfo", "null", "num", "termIfThenElse", "term-_", "term_&&&_",
    "term_*_", "term_++_", "term_+_", "term_<<<_", "term_^^^_", "term_|||_",
    "term_≠_"].map Name.mkSimple)

private partial def checkGeneratedSyntax (stx : Syntax) : CommandElabM Unit := do
  if stx.isMissing then throwError "missing native model syntax"
  if stx.isIdent then
    let name := stx.getId.eraseMacroScopes.toString
    if name == "sorryAx" || name.endsWith ".sorryAx" then
      throwError "unsupported native axiom reference"
  if let .node _ kind children := stx then
    unless generatedKinds.contains kind do
      throwError "unsupported native model syntax: {kind}"
    if kind == ``Lean.Parser.Command.optDeriving || kind == ``Lean.Parser.Termination.suffix then
      let arity := if kind == ``Lean.Parser.Command.optDeriving then 1 else 2
      unless children.size == arity &&
          children.all (fun child => child.isOfKind `null && child.getArgs.isEmpty) do
        throwError "unsupported native deriving/termination annotation"
    for child in children do checkGeneratedSyntax child

private def checkDeclaration (cmd : Syntax) : CommandElabM Unit := do
  checkGeneratedSyntax cmd
  unless cmd.isOfKind ``Lean.Parser.Command.declaration do
    throwError "native source only permits record/def declarations"
  let record := cmd[1].isOfKind ``Lean.Parser.Command.structure
  unless record || cmd[1].isOfKind ``Lean.Parser.Command.definition do
    throwError "native source only permits record/def declarations"
  let plain ← parseCommand "def placeholder := 0"
  let noinline ← parseCommand "@[noinline] def placeholder := 0"
  unless sameShape cmd[0] plain[0] || (!record && sameShape cmd[0] noinline[0]) do
    throwError "native source only permits plain records and plain/noinline defs"
  let declId := cmd[1][1]
  unless declId.isOfKind ``Lean.Parser.Command.declId && declId[0].isIdent &&
      declId[0].getId.isAtomic && declId[1].getArgs.isEmpty do
    throwError "native declarations must have simple names and no universe parameters"
  if record && ![`Inputs, `State, `Outputs, `Evaluation, `StateGroup0, `StateGroup1,
      `StateGroup2, `StateGroup3, `StateGroup4, `StateGroup5, `StateGroup6,
      `StateGroup7].contains declId[0].getId then
    throwError "unexpected native record name"
  if !record then
    let name := declId[0].getId.toString
    let indexed := ["wire", "next"].any fun stem =>
      let suffix := name.drop stem.length |>.toString
      name.startsWith stem && !suffix.isEmpty && suffix.toList.all Char.isDigit
    unless indexed || ["nextState", "outputs", "evaluate", "initialState"].contains name do
      throwError "unexpected native definition name: {name}"

elab "import_native_sparkle " path:str " as " target:ident : command => do
  let source ← IO.FS.readFile path.getString
  let ast ← Parser.testParseModule (← getEnv) path.getString source
  unless ast.isOfKind ``Lean.Parser.Module.module && ast.getArgs.size == 2 do
    throwError "expected parsed Lean module"
  match ast[0] with
  | `(Lean.Parser.Module.header| import Std) => pure ()
  | _ => throwError "native source must have exactly `import Std`"
  let commands := ast[1].getArgs
  unless commands.size ≥ 6 do throwError "empty native source"
  match commands[0]! with
  | `(command| namespace Task2RTL) => pure ()
  | _ => throwError "expected namespace Task2RTL"
  unless commands.back!.isOfKind ``Lean.Parser.Command.eoi do
    throwError "missing native source terminator"
  match commands[commands.size - 2]! with
  | `(command| end Task2RTL) => pure ()
  | _ => throwError "expected end Task2RTL"
  let options := #["set_option maxRecDepth 65536", "set_option maxHeartbeats 0",
    "set_option linter.unusedVariables false"]
  for (option, index) in options.zipIdx do
    unless sameShape commands[index + 1]! (← parseCommand option) do
      throwError "unexpected native model option"
  for cmd in commands[4:commands.size - 2] do checkDeclaration cmd
  elabCommand (← `(command| namespace $target))
  withReader (fun ctx => { ctx with fileName := path.getString, fileMap := FileMap.ofString source }) do
    for cmd in commands[1:commands.size - 2] do elabCommand cmd
  elabCommand (← `(command| end $target))

end SparkleProof
