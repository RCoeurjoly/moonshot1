import Lean

open Lean Meta Elab Tactic

/-- Propose reflexivity without eagerly normalizing in the elaborator.
    The final Lean kernel still checks the complete equation. -/
elab "kernel_rfl" : tactic => do
  let goal ← getMainGoal
  let some (_, _, rhs) := (← whnf (← goal.getType)).eq? | throwError "expected equality"
  goal.assign (← mkEqRefl rhs)
  replaceMainGoal []

/-- Submit an explicit proof candidate directly to final kernel checking.
    Avoids expensive elaborator unification between large circuit records. -/
elab "kernel_exact " candidate:term : tactic => withMainContext do
  let goal ← getMainGoal
  let proof ← Term.elabTerm candidate none
  Term.synthesizeSyntheticMVarsNoPostponing
  goal.assign proof
  replaceMainGoal []
