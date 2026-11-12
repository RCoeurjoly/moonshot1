# What changed for opt-full

The baseline exporter, diagnostics and native-trace driver are unchanged shared
sources. The same Sparkle pin and same Lean versions are used.

The candidate required standard Yosys lowering of reductions/logical gates and
splitting partial internal nets at driver boundaries. Without these, the pinned
path produced an ill-typed zero comparison and a one-bit shift that differed
between C promotion and strict BitVec evaluation. The first internal divergence
was buffer24 data1 bit4 at edge6; the native result completed after36 rather than
436 edges. Normalization regression fixtures and the complete universal transition
proof guard these cases. No private operator implementation was added.

Candidate state/name correspondence is metadata-driven, including exact Yosys
net-bit aliases for the output word. Its adapter command has a distinct name to
avoid collision with the baseline elaborator. The reference bridge adds two
finite BitVec lemmas and adjusts normalization. It reuses the established generic
memory and word-write lemmas and candidate temporal theorem.

The direct proof adds five generic mux/append lemmas, an explicit generated
embedding, structural assembly and ordinary run induction. Its actual theorem
closure and its module imports are both checked for independence from reference
circuit models. The arbitrary-state relation is stated explicitly; no equality
between unrelated raw states is claimed.

Resource measurements use one warm run per path with four field workers and two
Lean threads each. Existing dependencies and temporal-proof libraries are reused.
Wall time and maximum process RSS are observations, not proof-engineering effort.
The baseline wrapper additionally asks Lake to check its retained library, so
setup accounting is not identical. No statistical speed or strict less-work claim
is made. Failed proof experiments are excluded from the successful run timing;
the progress ledger records the interventions. Active engineering time was not
instrumented. Source/generator line counts are reported only as size information.
