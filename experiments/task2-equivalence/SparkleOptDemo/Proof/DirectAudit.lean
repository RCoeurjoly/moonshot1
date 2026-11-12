import Lean
open Lean Elab Command

-- Audit actual transitive proof dependencies, not merely imported modules.
elab "audit_native_dependencies " theoremName:ident : command => do
  let env ← getEnv
  let root := theoremName.getId
  let resolved ← resolveGlobalConstNoOverload theoremName
  let mut pending := #[resolved]
  let mut visited : Std.HashSet Name := {}
  while !pending.isEmpty do
    let name := pending.back!
    pending := pending.pop
    if visited.contains name then continue
    visited := visited.insert name
    let label := name.toString
    if label.startsWith "Task2." || label.startsWith "LeanFlow." ||
        label == "SparkleProof.evaluate" then
      throwError "direct proof depends on a retained circuit: {name}"
    if let some info := env.find? name then
      pending := pending ++ info.type.getUsedConstants
      if let some value := info.value? (allowOpaque := true) then
        pending := pending ++ value.getUsedConstants
    else
      throwError "unresolved direct proof dependency: {name}"
  logInfo m!"NATIVE_DEPENDENCIES_CHECKED {root}: {visited.size} declarations; no retained circuit"
