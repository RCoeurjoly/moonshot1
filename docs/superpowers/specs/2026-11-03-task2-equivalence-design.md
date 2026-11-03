# Task 2 equivalence and proof reuse design

The first result is a universal Lean proof for the existing Task 2 computation, followed by one compilation change whose correctness can be established with less additional proof work.

The reference is the existing MatmulModule in /home/roland/LLM2FPGA/src/matmul.py. Its adapter supplies two tensors of shape [16] and dtype int32. This is a dot product with a scalar int32 result. The original floating model, quantization quality, and TinyStories verification are outside this experiment.

## Accepted approach and planned choices

Use the already frozen, Nix-reproducible Task 2 in /home/roland/LLM2FPGA as the baseline. Import its PyTorch model and generated implementation into Lean and relate both to the same word-level computation. Keep the existing Task 2 Handshake compiler route for this experiment; the Calyx route in clean-LLM2FPGA is a later integration target.

For the first change, add Yosys opt -full after a shared, recorded normalization stage. Emit candidate RTL2 from the same baseline compiler output and re-import it. Require a substantive change to normalized logic or state: a different filename, serialization, or hash alone does not count.

Use Lean for the baseline and candidate correctness results. Run EQY on the same baseline/candidate pair as a comparison. An EQY verdict is additional evidence with its own trusted base; it must not be inserted into Lean as an equivalence axiom.

These are the alternatives considered:

- Reprove the candidate directly against the imported source, reusing shared arithmetic, protocol and invariant lemmas. This is the primary experiment and measures maintenance of the Lean argument.
- Prove candidate-to-baseline refinement and compose it with baseline correctness. A checked Lean refinement can provide this route; EQY supplies a separate implementation comparison.
- Verify the entire compiler. This would expand the scope substantially and is deferred.

## Exact contract

- Both vectors have 16 signed int32 elements, represented by their complete 32-bit words.
- The reference reduction uses multiplication and addition modulo 2^32. Establish this as the explicit contract of the pinned PyTorch operation; verify interoperability with overflow and negative-input controls. Stop if the captured operation has different semantics.
- Quantify over all pairs of input vectors, including overflow cases. Do not specialize the model to the sample vectors or replace integer arithmetic with real or floating-point arithmetic.
- Verify one transaction from the initialized kernel state. Initial RAM contents represent the two input vectors; all source-defined initial bits remain respected, and unspecified bits are not silently forced to zero.
- Follow the existing testbench environment: four rising clock edges of reset, start held until the input handshake accepts it, out0_ready and in2_st0_ready held high, and in2_st0_done_valid held low.
- The observed result is the data associated with the first accepted in2_st0_valid event. out0_valid is a different handshake signal and cannot substitute for the data result.
- Prove that a first result occurs within a derived finite cycle bound and that its 32-bit data equals the reference. The simulation timeout of 10000 cycles is not a proved bound.
- Prove that the initial-state relation is inhabited for every pair of input vectors. An impossible precondition cannot satisfy the milestone.
- The first transformation preserves this external cycle/protocol behavior. Variable-latency transformations, backpressure, repeated transactions and reset during execution are later extensions.

## Trust and artifact boundaries

Lean checks the theorem about the actual imported definitions. PyTorch capture, source/operator correspondence, RTL elaboration, Yosys normalization/export, and the hardware importer must each be identified as proved, independently checked, or trusted. Sample parity tests are correspondence evidence rather than universal source-translation proofs.

No theorem may assume model/RTL equivalence, its own desired output, or completion. Audit all transitive axiomatic dependencies, permitting only the declared standard Lean axioms and any explicitly documented reflective execution trust. Do not use trusted solver answers as substitutes for proof terms.

Record the existing baseline's Nix derivations, source/store paths, tool versions, compiler arguments and RTL hashes. Record the memory mapping, derived Lean import artifacts, theorem statements and proof artifacts alongside them. A final verdict must identify the exact baseline and candidate artifacts it covers. This provenance binding does not require freezing Task 2 again.

## Existing evidence and concrete gaps

Task 2 is already frozen and reproducible with Nix in /home/roland/LLM2FPGA. The original repository's tracked HEAD at planning time is b6dc8abcc023e241016a1fe19564b0d5af0c25b4. Use the existing derivations and their actual source/store paths as the baseline; no repository snapshot or second compiler setup is required.

The Task 2 flake exports matmul-sv-sim. Its RTL and compiler intermediates are dependencies of that derivation and can be located through the Nix derivation graph. Reuse those artifacts directly. If TorchLean needs a graph or saved export for interchange, derive it from the same Nix-pinned model and PyTorch environment and record its correspondence to the existing compiler input. That conversion is Lean import work; it does not replace the baseline or change its compiler inputs.

The inspected TorchLean commit f37cbc5aca8e79943b0ef0e3d3499ca9719d7c2b supports integer tensor storage and matmul shape inference, but NN.IR.Interpreter.reference.arithmetic supplies a dictionary only for binary formats. Integer matmul evaluation therefore needs a narrow, explicit semantic extension. Implement it over the imported, checked graph; reject unsupported nodes instead of supplying fake arithmetic operations.

Use Lean 4.35.0, with TorchLean's pinned dependency closure. The previous hardware importer run used Lean 4.19.0, so its small runtime must be checked and, if needed, ported to the same Lean 4.35.0 environment. Do not combine incompatible compiled Lean objects.

Reuse the inspected xiangshan2Lean importer at a1299b564831e571b9b80f816219ae06c91db342 and the retained hardware-import examples. Local /tmp checkouts are caches, not durable dependencies.

## Completion and measurement

The milestone succeeds when both baseline_correct and candidate_correct replay from frozen artifacts, the candidate has a substantive compiler-produced change, and the maintenance record demonstrates lower incremental proof effort.

Record source/import setup separately from proof construction. For baseline and candidate proof work, record actor, active time, interventions, new or changed semantic/proof obligations, shared theorem reuse, and proof-checking time. Report missing effort data as missing. Lower checking time or fewer lines alone does not demonstrate lower engineering effort.

For automated comparisons, run three warm repetitions with the same machine, tool pins and a 600-second per-run limit. Report the median, peak RSS, cache mode, and claim being checked. Record first-run/setup costs separately. EQY may prove, produce a counterexample, time out, or encounter unsupported constructs; only an actual proof supports the corresponding refinement claim.

Write implementation and generated artifacts under /home/roland/moonshot1/experiments/task2-equivalence. Read the original repositories without modifying them. The only deliverables of the present planning task are this design and its implementation plan.

## References

- [Task 2 model](/home/roland/LLM2FPGA/src/matmul.py)
- [Task 2 adapter](/home/roland/LLM2FPGA/src/matmul_adapter.py)
- [Task 2 testbench](/home/roland/LLM2FPGA/sim/tb_main.sv)
- [Task 2 pipeline](/home/roland/LLM2FPGA/nix/pipeline.nix)
- [Existing Lean research](/home/roland/clean-LLM2FPGA/research/lean-equivalence.org)
- [Literature survey](../../../research/arxiv-neural-networks-lean-2026-11-03.org)
- [EQY strategies](https://yosyshq.readthedocs.io/projects/eqy/en/latest/strategies.html)
- [EQY refinement and initialization semantics](https://yosyshq.readthedocs.io/projects/eqy/en/latest/xprop.html)

