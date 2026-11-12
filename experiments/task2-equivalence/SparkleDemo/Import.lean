import Tools.SVParser
import Sparkle.Backend.CSim
import Sparkle.Backend.Verilog

/-! Diagnostic exports and Sparkle's C backend. The native Lean model is
    generated separately by ExportTask2 and used by both traces and proofs. -/
def main (args : List String) : IO Unit := do
  let [source, output] := args
    | throw (IO.userError "usage: sparkle-import task2.sv output-dir")
  let design ← IO.ofExcept (Tools.SVParser.Lower.parseAndLowerHierarchical
    (← IO.FS.readFile source))
  unless design.modules.length == 1 do
    throw (IO.userError "expected exactly one flattened module")
  let some hardwareModule := design.modules.head?
    | throw (IO.userError "empty Sparkle design")
  unless hardwareModule.name == "task2" do throw (IO.userError "unexpected top module")
  let out := System.FilePath.mk output
  IO.FS.createDirAll out
  IO.FS.writeFile (out / "sparkle-ir.txt") (reprStr design)
  IO.FS.writeFile (out / "sparkle.c") (Sparkle.Backend.CSim.toCDesign design)
  IO.FS.writeFile (out / "roundtrip.sv") (Sparkle.Backend.Verilog.toVerilogDesign design)
  IO.println "SPARKLE_IMPORTED: diagnostic IR, C model and round-trip Verilog"
