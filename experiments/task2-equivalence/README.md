# Task 2 equivalence experiment

The existing Task 2 baseline is attached and the imported source semantics are proved. The hardware import, initialization/RAM proofs and concrete RTL correspondence controls pass. **The universal accelerator result/completion theorem and the proof-reuse milestone remain open.**

The source is the original `MatmulModule` and adapter in `/home/roland/LLM2FPGA`, revision `b6dc8abcc023e241016a1fe19564b0d5af0c25b4`: two int32 vectors of length 16 and one scalar result. Arithmetic uses complete 32-bit words with modular multiplication/addition. The experiment preserves the original repositories.

Verified so far:

- The existing Nix simulation reproduces `PASS`, expected/got **816**.
- The derived PyTorch export reproduces the original Torch-MLIR input byte for byte. Its pure Lean `Program` agrees with TorchLean's typed import.
- `Task2.source_agrees` holds for every pair of word vectors. TorchLean's missing integer-matmul arithmetic is supplied by a narrow local evaluator that rejects unsupported graphs.
- The imported hardware has 6,318 nodes and 453 state fields after checked single-clock normalization. `initial_exists` supplies a witness for every input pair; all other raw initial registers remain unconstrained in the initial relation.
- `memoryA_preserved` and `memoryB_preserved` hold for arbitrary raw state and any number of steps, including reset.
- Seven controls agree between pinned PyTorch, Lean and original-RTL Verilator simulation: zeros, negatives, product overflow, accumulation overflow, cancellation and Task 2's sample. The complete handshake traces agree. Their accepted payloads occur after 436 rising edges, including four reset edges. This observed timing is not yet a universal completion theorem.

`source_agrees` uses `propext`, `Classical.choice`, `Quot.sound`; the RAM lemmas use `propext`, `Quot.sound`; initialization existence has no axioms. The runner rejects undeclared axioms and treats timeouts/tool failures as inconclusive rather than proofs or counterexamples.

Run from this directory:

```sh
nix develop path:. --command python3 scripts/run.py attach --task2 /home/roland/LLM2FPGA --out build
nix develop path:. --command python3 scripts/run.py reference --out build
nix develop path:. --command python3 scripts/run.py hardware --design baseline --out build
nix develop path:. --command python3 -m unittest discover -s tests -p test_experiment.py -v
```

Lake uses the committed dependency manifest, including TorchLean `f37cbc5…`, FloatLib `8c88715…`, and Lean 4.35.0. On a fresh checkout, let Lake fetch those locked dependencies; obtain Mathlib's matching caches if needed. Local `.lake` and `/tmp` directories are caches, not source pins. The full test suite requires the generated hardware modules from the preceding commands.

`build/manifest.json` names the original Nix derivations and artifact hashes. Stage results (`reference-result.json`, `hardware-baseline-result.json`) bind claims, commands, logs, per-process peak RSS and artifact identities. Generated Lean modules live in `build/generated/Task2/Imported`. The hardware result distinguishes universal RAM/initialization lemmas from numerical correspondence controls. No `baseline_correct` or `candidate_correct` theorem is currently published.

The original Task 2 SV/simulation derivations reproduce. Its older bitstream-tool Slang dependency currently fails a fixed-output source hash check; those original hashes were preserved. Verification instead uses the installed ABI-matched Yosys/Slang 0.66 closure, pinned as a separate content-identified Nix input. Moving this experiment to another host requires retaining that Nix closure as well as making the original baseline repository available. `tool-pins.json` records the distinction.

PyTorch/operator correspondence, RTL elaboration, Yosys normalization and importers remain declared trust boundaries. The clock-lifting pass runs only after checking every original register uses the same positive-edge clock. Read-only input RAMs preserve their unknown initial bits. A small adapter corrects the importer's handling of Yosys's zero-port bitmap representation, while genuine asynchronous writes remain rejected.

The remaining work follows the [implementation plan](../../docs/superpowers/plans/2026-11-03-task2-equivalence.md): prove the baseline result and first completion for every permitted initial state, make a substantive compiler change, prove the candidate, compare EQY under the same initialized-memory contract, and measure proof-maintenance effort. Concrete traces or lower replay time alone do not satisfy that milestone.
