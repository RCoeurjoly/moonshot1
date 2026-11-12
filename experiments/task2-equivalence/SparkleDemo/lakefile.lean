import Lake
open Lake DSL

package sparkleDemo

require sparkle from git
  "https://github.com/Verilean/sparkle" @ "1614cee83ac586ca9a0626cd4af13bfef7347c3a"

lean_lib SparkleDemo where
  srcDir := "."
  roots := #[`NativeExport]

@[default_target]
lean_exe «sparkle-import» where
  root := `Import

lean_exe «native-smoke» where
  root := `NativeSmoke

lean_lib ImportedCircuit where
  srcDir := "build/native"
  roots := #[`Task2RTL]

lean_exe «native-traces» where
  root := `NativeTraces
