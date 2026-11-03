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
