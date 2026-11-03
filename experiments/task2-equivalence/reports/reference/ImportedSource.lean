import NN.IR.Program

namespace Task2.Imported
def graphIdentity : String := "04b531bde5f069903a397c80b484920f18ca8ad564364b4bdf0e811fde524fb6"
def sourceProgram : NN.IR.Program where
  graph := { nodes := #[
    { id := 0, parents := #[], kind := .input, outShape := [16] },
    { id := 1, parents := #[], kind := .input, outShape := [16] },
    { id := 2, parents := #[0, 1], kind := .matmul, outShape := [] }
  ] }
  dtypes := #[.integer true (some 32), .integer true (some 32), .integer true (some 32)]
  inputs := #[0, 1]
  outputs := #[2]
  primitives := #[none, none, none]
end Task2.Imported
