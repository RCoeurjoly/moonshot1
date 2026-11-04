The first technical milestone is demonstrated: both the existing Task 2 circuit and an actual compiler variant have universal, kernel-checked equivalence proofs. The stricter claim that the second proof took less engineering work is **inconclusive**, because active work time was not instrumented.

| Result | Baseline | `opt -full` candidate |
|---|---:|---:|
| Public theorem | `Task2.baseline_correct` | `Task2.candidate_correct` |
| Accepted result bound, including reset | 436 edges | 436 edges |
| Distinct checked circuit cuts | 5,077 | 4,907 |
| Checked complete transitions | 436 | 436 |
| Historical composition attempt median (cache binding absent) | 81.84 s | 72.43 s |
| Fresh proof-stage wall time | 655.63 s | 588.80 s |
| Largest recorded process RSS | 5,740,988 KiB | 5,508,768 KiB |
| Physical registered bits | 6,754 | 5,738 |
| Physical mux cells | 1,193 | 211 |

The theorem covers arbitrary complete int32 input words, arithmetic modulo 2^32, all permitted unspecified register initialization, four reset edges, the fixed ready/done protocol, and the first accepted result. Initialized-state existence is proved for every input pair. It is a proof of one fixed transaction under this protocol, with declared capture/elaboration/import trust boundaries. The three standard Lean axioms are `propext`, `Classical.choice`, `Quot.sound`.

The proof approach emits a universally symbolic trajectory over the actual imported circuit. Lean checks every distinct local circuit equation and transition, then composes first-result and arithmetic facts. Python's normalized expressions are proposals, never an authority for the verdict. The optimized circuit reused the same generator and unchanged word/source/device definitions; maintenance added primitive simplifications and corrected a proof-method selector. The failed candidate attempt is retained and excluded from warm replay medians, not erased from the effort record.

`comparison.json` contains the final serial three-run measurements, artifact identities, cache/backend descriptions and EQY status. The six historical Lean composition commands completed, but their consumed cache identities were not recorded. Their attempt timings are retained; replay verdicts are inconclusive and proved-runtime medians are null. New checks/replays enforce cache attestations; no replacement measurements are claimed. The immutable fresh full-proof results above are unchanged. All three EQY attempts timed out at 600 seconds; its proved-runtime median is null. EQY is a supplementary toolchain comparison with a trusted shared-memory lift and driver. Partial partitions, failed runs and timeouts establish no extra equivalence claim. Neither faster replay nor fewer generated cuts measures engineering effort.

Evidence bundles live in `baseline-proof/`, `candidate-proof/`, `variant/`, and `comparison-evidence/`. Their hashes identify exact checked inputs and logs; original Nix artifacts remain the baseline. `effort.json` records interventions and missing active durations. Reproduction commands and the host-closure portability constraint are in the experiment README.

The next experiment should measure active engineering time from its start, apply a second substantive pipeline transformation, and record every failed proof attempt and changed obligation. The key scaling experiment is then to replace repeated finite trajectories with reusable operation-level refinement and controller invariants. A quantized matmul/requantization boundary is a suitable next semantic target before attempting a TinyStories block. Only measured gains across such changes would justify the broader claim that formal equivalence accelerates accelerator design.
