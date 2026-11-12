# Sparkle opt-full experiment

The user approved importing the frozen Yosys `opt -full` candidate through
Sparkle, proving the same universal single-transaction contract and exact
436-edge result, then attempting direct equivalence between the two Sparkle
models. Work stays in SparkleOptDemo. Both existing demos remain byte-identical.

Reuse the exact original optimized RTL and recorded physical checkpoint;
verify its hashes and reproduce the structural statistics. Share the pinned
Sparkle exporter and independent trace comparison helpers by importing their
unchanged sources. Keep dependencies, native model, controls, compiled proof
modules, logs and reports separate. Operator semantics continue to come only
from upstream `Tools.SVParser.VerifyEmit.denote`.

First prove all 441 reference next-state fields and five outputs against the
retained candidate model. Derive names, widths, memory indices and output-word
index from metadata; do not retain baseline's 453/451/380 constants. Compose the
retained candidate temporal theorem only after full transition equality.
Require three-way controls, fresh-source checks, output mutation rejection and
axiom audits allowing only propext, Classical.choice and Quot.sound.

Then derive a proposed relation between baseline and optimized native states
from actual register transformations. Check it with Lean, without using the
old candidate reference theorem in the direct transition argument. If removed
or merged state prevents arbitrary-state equality, establish an appropriate
invariant/reachable-state relation. Record the precise scope of any direct
result separately from the reference-based candidate proof.

Compare changed handwritten lemmas/generators and measured checker wall time
and peak process memory. Keep shared temporal-library setup separate from new
bridge checking; generated lines are not an engineering-time measurement.
Do not infer FPGA area or timing from normalized circuit statistics.
