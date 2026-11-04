import Lean

open Lean

unsafe def main (args : List String) : IO Unit := do
  let some module := args.head? | throw (IO.userError "module argument required")
  initSearchPath (← findSysroot)
  let env ← importModules #[{ module := module.toName }] {}
  for name in env.allImportedModuleNames do
    IO.println s!"{name}\t{← findOLean name}"
