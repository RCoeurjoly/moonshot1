import Lake
open Lake DSL

package task2_equivalence where
  version := v!"0.1.0"

require TorchLean from git
  "https://github.com/lean-dojo/TorchLean" @ "f37cbc5aca8e79943b0ef0e3d3499ca9719d7c2b"

lean_lib Task2 where
  roots := #[`Task2.WordDot, `Task2.Source, `Task2.Hardware]

lean_lib Task2Imported where
  srcDir := "build/generated"
  roots := #[`Task2.Imported.Source]

lean_lib LeanFlow

lean_lib LeanFlowGenerated where
  srcDir := "build/lean-flow/library"
  roots := #[`LeanFlow.Bridge]

lean_lib LeanFlowRetained where
  srcDir := "build/lean-flow/retained"
  roots := #[`Task2.Baseline, `Task2.Trace, `Task2.ProofTools,
    `Task2.Imported.BaselineCore, `Task2.Imported.BaselineAdapter,
    `Task2.Imported.BaselineTrace, `Task2.Imported.BaselineInitial,
    `Task2.Imported.BaselineFinalArithmetic, `Task2.Imported.BaselineTraceCorrect] ++
    (Array.range 51).map (fun i => Lean.Name.str `Task2.Imported s!"BaselineCuts{i}") ++
    (Array.range 22).map (fun i => Lean.Name.str `Task2.Imported s!"BaselineTransitions{i}")
