import Lean
import Mathlib.Tactic.ToExpr

set_option maxRecDepth 65536

namespace LeanFlow.SMT

inductive Ty where
  | bits (width : Nat)
  | boolean
  | memory (addressWidth width : Nat)
  deriving BEq, DecidableEq, Repr, Inhabited, Lean.ToExpr

structure Field where
  name : String
  sort : Ty
  deriving BEq, Repr, Inhabited, Lean.ToExpr

structure Node where
  op : String
  sort : Ty
  args : Array Nat := #[]
  value : Nat := 0
  deriving BEq, Repr, Inhabited, Lean.ToExpr

structure Program where
  name : String
  inputs : Array Field
  states : Array Field
  outputs : Array Field
  nodes : Array Node
  outputNodes : Array Nat
  nextStateNodes : Array Nat
  initializerAssertions : Nat := 0
  deriving BEq, Repr, Lean.ToExpr

private inductive SExpr where
  | atom (text : String)
  | list (items : Array SExpr)
  deriving BEq, Repr, Inhabited

private def pushExpr (expression : SExpr) (stack : List (Array SExpr))
    (roots : Array SExpr) : List (Array SExpr) × Array SExpr :=
  match stack with
  | [] => ([], roots.push expression)
  | frame :: rest => (frame.push expression :: rest, roots)

/-- Reads the unquoted, comment-bearing S-expression fragment emitted by Yosys.
    It is a parser, not an SMT solver. -/
private def sexprs (text : String) : Except String (Array SExpr) := do
  let mut stack : List (Array SExpr) := []
  let mut roots := #[]
  let mut atom := ""
  let mut comment := false
  for character in text.toList do
    if comment then
      if character == '\n' then comment := false
    else if character.isWhitespace || character == '(' || character == ')' || character == ';' then
      if !atom.isEmpty then
        (stack, roots) := pushExpr (.atom atom) stack roots
        atom := ""
      if character == ';' then comment := true
      else if character == '(' then stack := #[] :: stack
      else if character == ')' then
        match stack with
        | [] => throw "SMT: unmatched closing parenthesis"
        | frame :: rest => (stack, roots) := pushExpr (.list frame) rest roots
    else if character == '|' || character == '"' then
      throw "SMT: quoted symbols and strings are outside this FunctionalIR fragment"
    else atom := atom.push character
  if !atom.isEmpty then (stack, roots) := pushExpr (.atom atom) stack roots
  unless stack.isEmpty do throw "SMT: unclosed expression"
  pure roots

private def atom : SExpr → Except String String
  | .atom value => .ok value
  | _ => .error "SMT: expected an atom"

private def items : SExpr → Except String (Array SExpr)
  | .list values => .ok values
  | _ => .error "SMT: expected a list"

private def natural (expression : SExpr) : Except String Nat := do
  let text ← atom expression
  match text.toNat? with
  | some value => pure value
  | none => throw s!"SMT: expected a natural number, got {text}"

private def readSort (expression : SExpr) : Except String Ty := do
  match expression with
  | .atom "Bool" => pure .boolean
  | .list values =>
    match values.toList with
    | [.atom "_", .atom "BitVec", width] =>
      let width ← natural width
      unless width > 0 do throw "SMT: bitvector width must be positive"
      pure (.bits width)
    | [.atom "Array", address, word] =>
      let .bits addressWidth ← readBitsSort address | throw "SMT: array address must be a bitvector"
      let .bits width ← readBitsSort word | throw "SMT: array word must be a bitvector"
      pure (.memory addressWidth width)
    | _ => throw "SMT: unsupported sort"
  | _ => throw "SMT: unsupported sort"
where
  readBitsSort (expression : SExpr) : Except String Ty := do
    let values ← items expression
    match values.toList with
    | [.atom "_", .atom "BitVec", width] =>
      let width ← natural width
      unless width > 0 do throw "SMT: bitvector width must be positive"
      pure (.bits width)
    | _ => throw "SMT: expected a bitvector sort"

private def literal (text : String) : Option (Ty × Nat) := do
  if text == "true" then return (.boolean, 1)
  if text == "false" then return (.boolean, 0)
  let (base, factor) ← if text.startsWith "#b" then some (2,1)
    else if text.startsWith "#x" then some (16,4) else none
  let digits := text.toList.drop 2
  if digits.isEmpty then none else do
    let value ← digits.foldlM (fun value character => do
      let digit ← if character >= '0' && character <= '9' then some (character.toNat - '0'.toNat)
        else if character >= 'a' && character <= 'f' then some (character.toNat - 'a'.toNat + 10)
        else if character >= 'A' && character <= 'F' then some (character.toNat - 'A'.toNat + 10)
        else none
      if digit < base then some (value*base+digit) else none) 0
    pure (.bits (digits.length*factor), value)

private def sameBits (arguments : Array Ty) (count : Nat) : Except String Nat := do
  unless arguments.size == count do throw "SMT: wrong operator arity"
  let some (Ty.bits width) := arguments[0]? | throw "SMT: operator requires bitvectors"
  unless arguments.all (· == .bits width) do throw "SMT: bitvector widths disagree"
  pure width

/-- Static operation typing, shared by parsing and execution. -/
def infer (op : String) (arguments : Array Ty) (parameter : Nat := 0)
    (resultWidth : Nat := 0) : Except String Ty := do
  match op with
  | "ite" =>
    match arguments.toList with
    | [.boolean, yes, no] =>
      unless yes == no do throw "SMT: ite branch sorts disagree"
      pure yes
    | _ => throw "SMT: invalid ite"
  | "concat" =>
    match arguments.toList with
    | [.bits a, .bits b] => pure (.bits (a+b))
    | _ => throw "SMT: invalid concat"
  | "extract" =>
    let width ← sameBits arguments 1
    unless resultWidth > 0 && parameter+resultWidth ≤ width do throw "SMT: invalid extract bounds"
    pure (.bits resultWidth)
  | "zero_extend" | "sign_extend" =>
    let width ← sameBits arguments 1
    unless resultWidth ≥ width do throw "SMT: shrinking extension"
    pure (.bits resultWidth)
  | "bvadd" | "bvsub" | "bvmul" | "bvudiv" | "bvurem" | "bvand" | "bvor" |
      "bvshl" | "bvlshr" | "bvashr" => pure (.bits (← sameBits arguments 2))
  | "bvxor" =>
    unless arguments.size ≥ 2 do throw "SMT: xor requires at least two operands"
    pure (.bits (← sameBits arguments arguments.size))
  | "bvnot" | "bvneg" => pure (.bits (← sameBits arguments 1))
  | "bvugt" | "bvuge" | "bvult" | "bvule" | "bvsgt" | "bvsge" | "bvslt" | "bvsle" =>
    let _ ← sameBits arguments 2
    pure .boolean
  | "=" | "distinct" =>
    match arguments.toList with
    | [a,b] =>
      unless a == b do throw "SMT: equality sorts disagree"
      match a with
      | .memory _ _ => throw "SMT: array equality is not implemented"
      | _ => pure .boolean
    | _ => throw "SMT: equality requires two operands"
  | "not" =>
    unless arguments == #[.boolean] do throw "SMT: invalid Boolean not"
    pure .boolean
  | "and" | "or" =>
    unless arguments.all (· == .boolean) do throw "SMT: invalid Boolean operands"
    pure .boolean
  | "select" =>
    match arguments.toList with
    | [.memory addressWidth width, .bits address] =>
      unless address == addressWidth do throw "SMT: memory address width disagrees"
      pure (.bits width)
    | _ => throw "SMT: invalid select"
  | "store" =>
    match arguments.toList with
    | [.memory addressWidth width, .bits address, .bits word] =>
      unless address == addressWidth && word == width do throw "SMT: memory write sorts disagree"
      pure (.memory addressWidth width)
    | _ => throw "SMT: invalid store"
  | _ => throw s!"SMT: unsupported operator {op}"

private structure Build where
  nodes : Array Node := #[]
  names : Std.HashMap String Nat := {}
  selectors : Std.HashMap String (Bool × Nat × Ty) := {}

private abbrev Lower := StateT Build (Except String)

private def emit (node : Node) : Lower Nat := do
  let index := (← get).nodes.size
  modify fun state => { state with nodes := state.nodes.push node }
  pure index

private partial def lower (expression : SExpr) : Lower Nat := do
  match expression with
  | .atom name =>
    if let some index := (← get).names[name]? then return index
    if let some (sort,value) := literal name then return ← emit ⟨"constant",sort,#[],value⟩
    throw s!"SMT: unbound atom {name}"
  | .list values =>
    let some head := values[0]? | throw "SMT: empty expression"
    if let .list indexed := head then
      let rest := values.toList.drop 1
      let [operand] := rest | throw "SMT: indexed operator requires one operand"
      let index ← lower operand
      let .bits width := (← get).nodes[index]!.sort | throw "SMT: indexed operator requires bits"
      let (op,parameter,resultWidth) ← match indexed.toList with
        | [.atom "_",.atom "extract",hi,lo] => do
          let hi ← natural hi; let lo ← natural lo
          unless lo ≤ hi do throw "SMT: invalid extract interval"
          pure ("extract",lo,hi-lo+1)
        | [.atom "_",.atom op,amount] => do
          unless op == "zero_extend" || op == "sign_extend" do throw "SMT: unsupported indexed operator"
          pure (op,0,width+(← natural amount))
        | _ => throw "SMT: malformed indexed operator"
      let sort ← infer op #[.bits width] parameter resultWidth
      return ← emit ⟨op,sort,#[index],parameter⟩
    let op ← atom head
    if let some (stateField,index,sort) := (← get).selectors[op]? then
      unless values.size == 2 && (← atom values[1]!) == (if stateField then "state" else "inputs") do
        throw "SMT: incorrect record selector"
      return ← emit ⟨if stateField then "state" else "input",sort,#[],index⟩
    let args ← (values.extract 1 values.size).mapM lower
    let current ← get
    let sorts := args.map fun index => current.nodes[index]!.sort
    let sort ← infer op sorts
    emit ⟨op,sort,args,0⟩

private def record (expression : SExpr) : Except String (String × Array Field) := do
  let values ← items expression
  match values.toList with
  | [.atom "declare-datatype",.atom name,constructors] =>
    let constructors ← items constructors
    unless constructors.size == 1 do throw "SMT: expected one record constructor"
    let fields ← items constructors[0]!
    unless (← atom fields[0]!) == name do throw "SMT: record constructor name disagrees"
    let fields ← (fields.extract 1 fields.size).mapM fun field => do
      match (← items field).toList with
      | [.atom selector,sort] => pure ⟨selector,← readSort sort⟩
      | _ => throw "SMT: malformed record field"
    pure (name,fields)
  | _ => throw "SMT: malformed datatype declaration"

private partial def initialSort (selectors : Std.HashMap String (Bool × Nat × Ty))
    (expression : SExpr) : Except String Ty := do
  match expression with
  | .atom value =>
    let some (sort,_) := literal value | throw "SMT: initializer must use literal words"
    pure sort
  | .list values =>
    match values.toList with
    | [.atom selector,.atom "main-initial"] =>
      let some (true,_,sort) := selectors[selector]? | throw "SMT: unknown initial-state selector"
      pure sort
    | [.atom "select",memory,address] => infer "select" #[← initialSort selectors memory,← initialSort selectors address]
    | _ => throw "SMT: unsupported initial-state expression"

/-- This first-order fragment rejects shadowing rather than implementing
    overloaded or locally rebound constructor/operator resolution. -/
private def reservedSymbol (name : String) : Bool :=
  ["!", "_", "as", "let", "exists", "forall", "match", "par",
   "Bool", "BitVec", "Array", "Pair", "pair", "first", "second", "inputs", "state",
   "declare-datatype", "declare-datatypes", "declare-const", "define-fun", "assert",
   "ite", "concat", "extract", "zero_extend", "sign_extend",
   "bvadd", "bvsub", "bvmul", "bvudiv", "bvurem", "bvand", "bvor", "bvxor",
   "bvnot", "bvneg", "bvshl", "bvlshr", "bvashr",
   "bvugt", "bvuge", "bvult", "bvule", "bvsgt", "bvsge", "bvslt", "bvsle",
   "=", "distinct", "not", "and", "or", "select", "store"].contains name ||
    (literal name).isSome

private def declareSymbol (known : Std.HashSet String) (name : String) :
    Except String (Std.HashSet String) := do
  if reservedSymbol name || known.contains name then
    throw s!"SMT: reserved or duplicate global symbol {name}"
  pure (known.insert name)

private def readProgram (roots : Array SExpr) : Except String Program := do
  let mut records : Std.HashMap String (Array Field) := {}
  let mut globals : Std.HashSet String := {}
  let mut definitions := #[]
  let mut assertions := #[]
  let mut initialType : Option String := none
  let mut pairDeclared := false
  for root in roots do
    let xs ← items root
    match xs.toList with
    | .atom "declare-datatype" :: _ =>
      let (name,fields) ← record root
      if records.contains name then throw "SMT: duplicate record type"
      globals ← declareSymbol globals name
      for field in fields do
        globals ← declareSymbol globals field.name
      records := records.insert name fields
    | [.atom "declare-datatypes",_,_] =>
      let expected ← sexprs "(declare-datatypes ((Pair 2)) ((par (X Y) ((pair (first X) (second Y))))))"
      unless !pairDeclared && expected == #[root] do throw "SMT: invalid or duplicate Pair declaration"
      pairDeclared := true
    | .atom "define-fun" :: .atom name :: _ =>
      globals ← declareSymbol globals name
      definitions := definitions.push xs
    | [.atom "declare-const",.atom "main-initial",.atom typ] =>
      if initialType.isSome then throw "SMT: duplicate initial-state constant"
      globals ← declareSymbol globals "main-initial"
      initialType := some typ
    | [.atom "assert",expression] => assertions := assertions.push expression
    | _ => throw "SMT: unsupported top-level command"
  unless definitions.size == 1 && pairDeclared do throw "SMT: expected one transfer function and Pair declaration"
  let definition := definitions[0]!
  let [.atom _,.atom name,parameters,result,body] := definition.toList | throw "SMT: malformed function"
  let [input,state] := (← items parameters).toList | throw "SMT: expected inputs and state parameters"
  let [.atom "inputs",.atom inputType] := (← items input).toList | throw "SMT: invalid inputs parameter"
  let [.atom "state",.atom stateType] := (← items state).toList | throw "SMT: invalid state parameter"
  let [.atom "Pair",.atom outputType,.atom returnedState] := (← items result).toList | throw "SMT: expected Pair result"
  unless returnedState == stateType && records.size == 3 do throw "SMT: unexpected record signature"
  let some inputs := records[inputType]? | throw "SMT: missing input record"
  let some states := records[stateType]? | throw "SMT: missing state record"
  let some outputs := records[outputType]? | throw "SMT: missing output record"
  if let some typ := initialType then
    unless typ == stateType do throw "SMT: initial constant has wrong type"
  let mut build : Build := {}
  for (fields,stateField) in [(inputs,false),(states,true)] do
    for index in [:fields.size] do
      let field := fields[index]!
      if build.selectors.contains field.name then throw "SMT: duplicate selector"
      build := { build with selectors := build.selectors.insert field.name (stateField,index,field.sort) }
  for assertion in assertions do
    let [.atom "=",left,right] := (← items assertion).toList | throw "SMT: only initial-word equalities are supported"
    unless initialType.isSome do throw "SMT: assertion has no declared initial constant"
    unless (← initialSort build.selectors left) == (← initialSort build.selectors right) do
      throw "SMT: initializer sorts disagree"
  let action : Lower (Array Nat × Array Nat) := do
    let mut body := body
    let mut reading := true
    while reading do
      match body with
      | .list xs =>
        if (match xs[0]? with | some (.atom "let") => true | _ => false) then
          let [.atom "let",bindings,next] := xs.toList | throw "SMT: malformed let"
          let [binding] := (← items bindings).toList | throw "SMT: only single-binding lets are supported"
          let [.atom name,value] := (← items binding).toList | throw "SMT: malformed binding"
          if (← get).names.contains name || globals.contains name || reservedSymbol name then
            throw "SMT: duplicate or shadowed binding"
          let index ← lower value
          modify fun state => { state with names := state.names.insert name index }
          body := next
        else reading := false
      | _ => reading := false
    let [.atom "pair",output,next] := (← items body).toList | throw "SMT: expected outputs/state pair"
    let values (expression : SExpr) (name : String) (fields : Array Field) : Lower (Array Nat) := do
      let xs ← items expression
      unless xs.size == fields.size+1 && (← atom xs[0]!) == name do throw "SMT: record result arity disagrees"
      let indices ← (xs.extract 1 xs.size).mapM lower
      for index in [:fields.size] do
        unless (← get).nodes[indices[index]!]!.sort == fields[index]!.sort do throw "SMT: record result sort disagrees"
      pure indices
    pure (← values output outputType outputs,← values next stateType states)
  let ((outputNodes,nextStateNodes),finished) ← action.run build
  pure ⟨name,inputs,states,outputs,finished.nodes,outputNodes,nextStateNodes,assertions.size⟩

def parse (text : String) : Except String Program := do
  readProgram (← sexprs text)

inductive Value where
  | bits (width : Nat) (word : BitVec width)
  | boolean (value : Bool)
  | memory (addressWidth width : Nat) (read : BitVec addressWidth → BitVec width)

def Value.sort : Value → Ty
  | .bits width _ => .bits width
  | .boolean _ => .boolean
  | .memory address width _ => .memory address width

def Value.asBits (width : Nat) : Value → Except String (BitVec width)
  | .bits actual word => if h : actual = width then .ok (h ▸ word) else .error "SMT: word width mismatch"
  | _ => .error "SMT: expected a bitvector value"

def Value.asBool : Value → Except String Bool
  | .boolean value => .ok value
  | _ => .error "SMT: expected a Boolean value"

def Value.asMemory (addressWidth width : Nat) : Value → Except String (BitVec addressWidth → BitVec width)
  | .memory address word read =>
    if ha : address = addressWidth then
      if hw : word = width then by cases ha; cases hw; exact .ok read
      else .error "SMT: memory word width mismatch"
    else .error "SMT: memory address width mismatch"
  | _ => .error "SMT: expected a memory value"

def valueAt (values : Array Value) (index : Nat) : Except String Value :=
  match values[index]? with
  | some value => .ok value
  | none => .error "SMT: missing value"

def bitsAt (width : Nat) (values : Array Value) (index : Nat) : Except String (BitVec width) := do
  (← valueAt values index).asBits width

def memoryAt (addressWidth width : Nat) (values : Array Value) (index : Nat) :
    Except String (BitVec addressWidth → BitVec width) := do
  (← valueAt values index).asMemory addressWidth width

/-- Ite keeps the value constructor outside the conditional. This preserves
    symbolic word-level evaluation without splitting every Boolean branch. -/
def choose (sort : Ty) (condition : Bool) (yes no : Value) : Except String Value := do
  match sort with
  | .bits width =>
    let a ← yes.asBits width; let b ← no.asBits width
    pure (.bits width (if condition then a else b))
  | .boolean =>
    let a ← yes.asBool; let b ← no.asBool
    pure (.boolean (if condition then a else b))
  | .memory address width =>
    let a ← yes.asMemory address width; let b ← no.asMemory address width
    pure (.memory address width (fun index => if condition then a index else b index))

def evalOp (node : Node) (args : Array Value) : Except String Value := do
  let resultWidth := match node.sort with | .bits width => width | _ => 0
  unless (← infer node.op (args.map Value.sort) node.value resultWidth) == node.sort do
    throw "SMT: operation result sort disagrees"
  if node.op == "ite" then
    return ← choose node.sort (← (← valueAt args 0).asBool) (← valueAt args 1) (← valueAt args 2)
  if node.op == "concat" then
    let .bits a x ← valueAt args 0 | throw "SMT: concat requires bits"
    let .bits b y ← valueAt args 1 | throw "SMT: concat requires bits"
    return .bits (a+b) (x ++ y)
  if node.op == "select" then
    let .memory address width read ← valueAt args 0 | throw "SMT: select requires memory"
    return .bits width (read (← bitsAt address args 1))
  match node.sort with
  | .bits width =>
    if node.op == "extract" || node.op == "zero_extend" || node.op == "sign_extend" then
      let .bits _ x ← valueAt args 0 | throw "SMT: indexed operation requires bits"
      return .bits width (match node.op with
        | "extract" => x.extractLsb' node.value width
        | "zero_extend" => x.setWidth width
        | _ => x.signExtend width)
    let a ← bitsAt width args 0
    if node.op == "bvnot" then return .bits width (~~~a)
    if node.op == "bvneg" then return .bits width (-a)
    if node.op == "bvxor" then
      let result ← (args.extract 1 args.size).foldlM (fun acc value => do pure (acc ^^^ (← value.asBits width))) a
      return .bits width result
    let b ← bitsAt width args 1
    pure (.bits width (match node.op with
      | "bvadd" => a+b | "bvsub" => a-b | "bvmul" => a*b
      | "bvudiv" => a.smtUDiv b | "bvurem" => a.umod b
      | "bvand" => a &&& b | "bvor" => a ||| b
      | "bvshl" => a <<< (Nat.min width b.toNat)
      | "bvlshr" => a >>> (Nat.min width b.toNat)
      | "bvashr" => a.sshiftRight (Nat.min width b.toNat)
      | _ => 0))
  | .boolean =>
    if node.op == "not" then return .boolean (!(← (← valueAt args 0).asBool))
    if node.op == "and" || node.op == "or" then
      let values ← args.mapM Value.asBool
      return .boolean (if node.op == "and" then values.all id else values.any id)
    let a ← valueAt args 0; let b ← valueAt args 1
    let result ← match a with
      | .bits width a => do
        let b ← b.asBits width
        pure (match node.op with
          | "=" => a == b | "distinct" => a != b
          | "bvugt" => decide (a.toNat > b.toNat) | "bvuge" => decide (a.toNat ≥ b.toNat)
          | "bvult" => decide (a.toNat < b.toNat) | "bvule" => decide (a.toNat ≤ b.toNat)
          | "bvsgt" => decide (a.toInt > b.toInt) | "bvsge" => decide (a.toInt ≥ b.toInt)
          | "bvslt" => decide (a.toInt < b.toInt) | "bvsle" => decide (a.toInt ≤ b.toInt)
          | _ => false)
      | .boolean a => do
        let b ← b.asBool
        pure (if node.op == "=" then a == b else a != b)
      | _ => throw "SMT: unsupported comparison"
    pure (.boolean result)
  | .memory address width =>
    let read ← (← valueAt args 0).asMemory address width
    let location ← bitsAt address args 1; let value ← bitsAt width args 2
    pure (.memory address width (fun index => if index == location then value else read index))

def evalNode (node : Node) (inputs state : Array Value)
    (lookup : Nat → Except String Value) : Except String Value := do
  let value ← match node.op with
    | "input" => valueAt inputs node.value
    | "state" => valueAt state node.value
    | "constant" => match node.sort with
      | .bits width => pure (.bits width (BitVec.ofNat width node.value))
      | .boolean => pure (.boolean (node.value != 0))
      | _ => throw "SMT: unsupported constant sort"
    | _ => evalOp node (← node.args.mapM lookup)
  unless value.sort == node.sort do throw "SMT: node value has wrong sort"
  pure value

structure Result where
  outputs : Array Value
  nextState : Array Value

def checkFields (fields : Array Field) (values : Array Value) : Except String Unit := do
  unless fields.size == values.size do throw "SMT: record size disagrees"
  unless fields.zipWith (fun field value => field.sort == value.sort) values |>.all id do
    throw "SMT: record value sort disagrees"

/-- A persistent binary store keeps kernel reduction logarithmic per access.
    Array.push has a list-based logical implementation, which made the large
    symbolic transition proof consume quadratic space. -/
inductive Store where
  | empty
  | leaf (word : Value)
  | branch (left right : Store)

def Store.write : Nat → Nat → Value → Store → Store
  | 0, _, value, _ => .leaf value
  | depth+1, index, value, tree =>
    let (left,right) := match tree with | .branch left right => (left,right) | _ => (.empty,.empty)
    if index.testBit depth then .branch left (right.write depth index value)
    else .branch (left.write depth index value) right

def Store.read : Nat → Nat → Store → Except String Value
  | 0, _, .leaf value => .ok value
  | depth+1, index, .branch left right =>
    if index.testBit depth then right.read depth index else left.read depth index
  | _, _, _ => .error "SMT: missing node value"

def runNodes (nodes : List Node) (inputs state : Array Value) (depth : Nat)
    (count : Nat := 0) (store : Store := .empty) : Except String (Nat × Store) :=
  match nodes with
  | [] => .ok (count,store)
  | node :: nodes => do
    let lookup index := if index < count then store.read depth index else .error "SMT: forward or missing node reference"
    let value ← evalNode node inputs state lookup
    runNodes nodes inputs state depth (count+1) (store.write depth count value)

/-- Executes the parsed transfer function at caller-supplied input/state.
    Assertions about the separate global `main-initial` are not assumptions on
    this argument. The Task2 startup contract supplies its input memories. -/
def eval (program : Program) (inputs state : Array Value) : Except String Result := do
  checkFields program.inputs inputs
  checkFields program.states state
  let depth := program.nodes.size.log2+1
  let (count,store) ← runNodes program.nodes.toList inputs state depth
  let lookup index := if index < count then store.read depth index else .error "SMT: missing result node"
  pure ⟨← program.outputNodes.mapM lookup,← program.nextStateNodes.mapM lookup⟩

end LeanFlow.SMT

open Lean Elab Command

elab "import_hardware_smt " path:str " as " identifier:ident : command => do
  let text ← IO.FS.readFile path.getString
  let program ← IO.ofExcept (LeanFlow.SMT.parse text)
  let name := (← getCurrNamespace) ++ identifier.getId
  liftCoreM <| addAndCompile (.defnDecl {
    name := name
    levelParams := []
    type := mkConst ``LeanFlow.SMT.Program
    value := toExpr program
    hints := .regular 0
    safety := .safe })
