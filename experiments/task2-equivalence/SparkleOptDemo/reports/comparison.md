# Resource observations

One warm run per path, four field workers and two Lean threads each. Existing
dependency and temporal-proof caches were available. These are successful
checking times, not active engineering time or a statistical speed benchmark.

| Proof path | Wall time | Maximum process RSS |
| --- | ---: | ---: |
| Sparkle baseline → reference | 168.02 s | 4.18 GiB |
| Sparkle opt-full → reference | 286.94 s | 3.90 GiB |
| Direct Sparkle native refinement | 130.70 s | 2.37 GiB |

The baseline wrapper additionally checks its retained library with Lake.
The optimized reference bridge was slower in this observation. The direct
proof has a different related-state claim, so its time is not a substitute
for a complete functional-correctness proof build. Maximum process RSS is
not the simultaneous sum across workers.

The same physical checkpoint reproduces registered bits **6,754 → 5,738** and
mux cells **1,193 → 211**. No physical FPGA area, timing or energy claim follows.

Two finite bit-vector lemmas and normalization adjustments support the
reference bridge; five generic mux/append lemmas support direct refinement.
The shared exporter was unchanged and no custom operator semantics were added.
Generated source sizes do not establish less proof-engineering effort.

Exact records and limitations: [comparison.json](comparison.json).
