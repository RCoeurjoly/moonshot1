# Task 2 equivalence experiment

**The frozen Task 2 baseline is proved equivalent to its imported int32 source semantics.** `Task2.baseline_correct` covers every pair of input vectors and every permitted initial hardware state. It proves the first accepted payload occurs after 436 rising edges, including four reset edges. The pipeline-change/proof-reuse experiment is in progress.

The source is the original `MatmulModule` and adapter in `/home/roland/LLM2FPGA`, revision `b6dc8abcc023e241016a1fe19564b0d5af0c25b4`: two int32 vectors of length 16 and one scalar result. Arithmetic uses complete 32-bit words with modular multiplication/addition. The experiment preserves the original repositories.

Verified so far:

- The existing Nix simulation reproduces `PASS`, expected/got **816**.
- The derived PyTorch export reproduces the original Torch-MLIR input byte for byte. Its pure Lean `Program` agrees with TorchLean's typed import.
- `Task2.source_agrees` holds for every pair of word vectors. TorchLean's missing integer-matmul arithmetic is supplied by a narrow local evaluator that rejects unsupported graphs.
- The imported hardware has 6,318 nodes and 453 state fields after checked single-clock normalization. `initial_exists` supplies a witness for every input pair; all other raw initial registers remain unconstrained in the initial relation.
- `memoryA_preserved` and `memoryB_preserved` hold for arbitrary raw state and any number of steps, including reset.
- Seven controls agree between pinned PyTorch, Lean and original-RTL Verilator simulation: zeros, negatives, product overflow, accumulation overflow, cancellation and Task 2's sample. The complete handshake traces agree.
- The universal hardware proof checks 5,077 distinct circuit chunks and all 436 transitions of a symbolic trajectory. The initial-state parameterization retains all unspecified registers and both initial start values. A separate arithmetic lemma identifies the final word with `dot32`; `FirstResult` excludes every earlier payload.
- A test-only payload mutation changes the sample result from 816 to 817. False equations submitted directly to the proof checker are rejected by the final kernel. Stale artifacts and weakened public theorem types are rejected.

`source_agrees` and `baseline_correct` use only `propext`, `Classical.choice`, `Quot.sound`; the RAM lemmas use `propext`, `Quot.sound`; initialization existence has no axioms. No external solver verdict or native reflective checker is used in these proofs. Python proposes normalized states and equations; Lean checks them against the actual imported circuit. The runner rejects undeclared axioms and treats timeouts/tool failures as inconclusive rather than proofs or counterexamples.

Run from this directory:

```sh
nix develop path:. --command python3 scripts/run.py attach --task2 /home/roland/LLM2FPGA --out build
nix develop path:. --command python3 scripts/run.py reference --out build
nix develop path:. --command python3 scripts/run.py hardware --design baseline --out build
nix develop path:. --command python3 scripts/run.py check --design baseline --out build --workers 8
nix develop path:. --command python3 -m unittest discover -s tests -p 'test*.py' -v
```

Lake uses the committed dependency manifest, including TorchLean `f37cbc5…`, FloatLib `8c88715…`, and Lean 4.35.0. On a fresh checkout, let Lake fetch those locked dependencies; obtain Mathlib's matching caches if needed. Local `.lake` and `/tmp` directories are caches, not source pins. The full test suite requires the generated hardware modules from the preceding commands.

`build/manifest.json` names the original Nix derivations and artifact hashes. Stage results bind claims, commands, logs, per-process peak RSS and artifact identities. Hardware import modules live in `build/generated/Task2/Imported`; proof certificates live in `build/proof/baseline`. The CLI compiles generated modules into the common Lean search path before compiling the public theorem in `Task2/Baseline.lean`. The hardware-import result distinguishes initialization/RAM lemmas and numerical controls from the complete theorem in `check-baseline-result.json`.

The fresh baseline proof stage passed all 84 compiler invocations in 655.63 seconds with eight workers. The largest recorded process RSS was 5,740,988 KiB; this is not the simultaneous memory total. This measures construction/checking of all generated proof modules with existing dependency caches, not a cache-only Lake build. Human/agent active proof-engineering time was not instrumented and remains missing.

`scripts/archive_evidence.py` retains hash-checked proof inputs and logs without changing their verdict. Run it after a proof stage before editing shared tooling if the previous result must remain independently inspectable. The committed report bundle retains the exact checked definitions and certificates; the existing Task 2 Nix provider remains the source/compiler baseline.

The original Task 2 SV/simulation derivations reproduce. Its older bitstream-tool Slang dependency currently fails a fixed-output source hash check; those original hashes were preserved. Verification instead uses the installed ABI-matched Yosys/Slang 0.66 closure, pinned as a separate content-identified Nix input. Moving this experiment to another host requires retaining that Nix closure as well as making the original baseline repository available. `tool-pins.json` records the distinction.

PyTorch/operator correspondence, RTL elaboration, Yosys normalization and importers remain declared trust boundaries. The clock-lifting pass runs only after checking every original register uses the same positive-edge clock. Read-only input RAMs preserve their unknown initial bits. A small adapter corrects the importer's handling of Yosys's zero-port bitmap representation, while genuine asynchronous writes remain rejected.

The remaining work follows the [implementation plan](../../docs/superpowers/plans/2026-11-03-task2-equivalence.md): import the `opt -full` candidate, prove it with the shared infrastructure, compare EQY under the same initialized-memory contract, and measure proof-maintenance effort. Concrete traces or lower replay time alone do not establish reduced engineering effort.
