# Task 2 equivalence experiment

**Both the frozen Task 2 hardware and an `opt -full` pipeline variant are proved equivalent to the imported int32 source computation.** `Task2.baseline_correct` and `Task2.candidate_correct` cover every pair of length-16 word vectors and every permitted initial hardware state. Both prove the first accepted result after 436 rising edges, including four reset edges.

The source is the original `MatmulModule` and adapter in `/home/roland/LLM2FPGA`, revision `b6dc8abcc023e241016a1fe19564b0d5af0c25b4`. Arithmetic is multiplication/addition modulo 2^32. The original repositories remain unchanged. This experiment verifies one transaction under the fixed startup/ready contract in `contract.json`; it does not yet cover backpressure, repeated transactions, TinyStories or quantization accuracy.

The actual pipeline treatment applies Yosys `opt -full` to the baseline's shared physical normalization checkpoint and emits new SystemVerilog. Candidate RTL is independently re-imported and proved. Registered bits fall **6,754 → 5,738** and mux cells **1,193 → 211**. These are normalized circuit statistics; FPGA area, frequency and energy have not been measured.

The decisive results and their limits:

- The existing Nix simulation reproduces expected/got **816**. Capturing the pinned PyTorch model reproduces the existing Torch-MLIR compiler input byte for byte. Its pure Lean `Program` agrees with TorchLean's typed import.
- `source_agrees` proves the checked integer graph computes `dot32`. Upstream TorchLean lacks the required int32 arithmetic; a narrow local evaluator supplies it and rejects unsupported graphs.
- Initialization is nonvacuous for every input pair. Other raw registers and the initial start bit remain universally quantified. Input-RAM preservation is proved for arbitrary state and any number of steps.
- The baseline proof checks **5,077** distinct circuit cuts and **436** complete transitions. The candidate checks **4,907** cuts and the same number of transitions. The final arithmetic and first-result proofs compose these into the public `Implements` theorems.
- Both theorems use only `propext`, `Classical.choice`, `Quot.sound`. Python proposes states/equations; Lean checks them against the imported circuit. External solver verdicts and native reflection do not enter these proofs.
- Seven controls match complete Lean/Verilator handshake traces for each design, including negative values, overflow, cancellation and the sample. A payload mutation changes 816 to 817. False proof submissions, stale inputs, weakened public theorem types and no-op variants are rejected.

`WordDot.lean`, `Source.lean`, `Hardware.lean` and `ProofTools.lean` are byte-identical between the proofs. Candidate maintenance required `distinct`/OR normalization, two elementary one-bit OR laws, and a correction to the proof-method selector. No handwritten candidate controller invariant was required. **Active engineering time was not instrumented, so the strict “less proof work” milestone remains inconclusive.** Replay speed and generated proof counts do not fill that measurement gap. `reports/effort.json` preserves the interventions and missing values.

Run from this directory:

```sh
nix develop path:. --command python3 scripts/run.py attach --task2 /home/roland/LLM2FPGA --out build
nix develop path:. --command python3 scripts/run.py reference --out build
nix develop path:. --command python3 scripts/run.py hardware --design baseline --out build
nix develop path:. --command python3 scripts/run.py check --design baseline --out build --workers 8
nix develop path:. --command python3 scripts/run.py variant --out build
nix develop path:. --command python3 scripts/run.py hardware --design candidate --out build
nix develop path:. --command python3 scripts/run.py check --design candidate --out build --workers 8
nix develop path:. --command python3 scripts/run.py compare --out build --repeats 3 --timeout 600
nix develop path:. --command python3 scripts/run.py report --out build
nix develop path:. --command python3 -m unittest discover -s tests -p 'test*.py' -v
nix develop path:. --command lake env lean Task2/Audit.lean
```

Lake uses the committed dependency manifest, including TorchLean `f37cbc5…`, FloatLib `8c88715…`, and Lean 4.35.0. Fetch locked dependencies and their matching Mathlib caches on a fresh checkout. The full suite needs generated hardware modules from the preceding stages. If the sandbox makes the default cache directory read-only, set `XDG_CACHE_HOME` to a writable directory.

`build/manifest.json` binds original Nix artifacts and the candidate. Proof results retain claim/type/axiom audits, exact inputs, commands, logs and peak process RSS. Generated modules are compiled into the Lean search path before checking `Task2/Baseline.lean` and `Task2/Candidate.lean`; they are not permanent Lake source targets. `scripts/archive_evidence.py` seals checked inputs/logs before later tooling edits. Committed `reports/baseline-proof` and `reports/candidate-proof` contain those retained inputs and certificates; no original baseline has been replaced.

Fresh generated proof stages, with existing dependency caches and eight workers, took **655.63 s** baseline and **588.80 s** candidate; maximum recorded process RSS was **5,740,988 KiB** and **5,508,768 KiB** respectively. These are single-process peaks, not simultaneous totals. The candidate also had a retained failed 126.15 s attempt before a proof-method fix. Setup and unsuccessful construction attempts are kept outside warm replay medians.

The comparison stage performs three serial warm runs with a 600 s limit per run. Lean rechecks final first-result/correctness composition from retained source in an isolated working directory, using prechecked dependency, cut and transition oleans. This is incremental composition replay, not a full fresh proof build or a cache-only Lake invocation. EQY runs separately in fresh work directories; its claim and trust base differ from Lean's. `reports/comparison.json` records the measurements and scoped verdict after the report stage.

EQY receives shared symbolic input words through a declared trusted read-only memory lift. Every constant vector pair remains possible; stability assumptions encode the initialized, immutable RAMs. The wrapper preserves four reset edges, unspecified initial start, fixed ready/done signals and the first accepted payload. No independent unknown RAM comparison or `setundef` to zero is used. EQY/SBY/Z3 verdicts are supplementary toolchain results. Failed partitions and timeouts never count as proofs or concrete mismatches; the concrete mutation control comes from the actual imported trajectory.

PyTorch/operator correspondence, RTL elaboration, Yosys normalization and importers remain trust boundaries. Clock lifting follows strict same-positive-clock checks. A narrow metadata adapter handles Yosys's zero-port bitmap representation; actual asynchronous writes are rejected. Candidate elaboration additionally runs `opt_expr`, `opt_muxtree`, `opt_clean` to remove unreachable process-temporary unknown branches, preserving unknown initial register/RAM values.

Original Task 2 SV/simulation derivations reproduce. Its older bitstream-tool Slang dependency currently fails an upstream source hash check; original hashes were preserved. Verification uses the installed ABI-matched Yosys/Slang 0.66 closure and EQY/SBY/Z3 closures as content-identified Nix inputs. Moving to another host requires retaining these closures and making the original baseline repository available; `tool-pins.json` records the dependencies.

The [implementation plan](../../docs/superpowers/plans/2026-11-03-task2-equivalence.md) and [design](../../docs/superpowers/specs/2026-11-03-task2-equivalence-design.md) define the acceptance criteria. The next experiment should instrument active proof-engineering time before starting a second transformation, then compare its measured incremental effort. Scaling the finite trace certificates to loops and larger models requires compositional invariants or reusable operation-level refinement lemmas.
