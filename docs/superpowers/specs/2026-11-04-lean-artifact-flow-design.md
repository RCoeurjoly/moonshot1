# Lean artifact flow

The user approved this architecture: Python exports the PyTorch graph; Lean parses and interprets that graph and the hardware SMT; Lean proves their observable computations agree. Keep the existing Task 2 proof and evidence immutable. Expose a small, readable entry point in experiments/task2-equivalence/LeanFlow and one short run command.

Python must not parse hardware SMT, emit the imported Lean models or supply model-specific graph semantics on the new path. Reuse TorchLean's Lean JSON/graph validation, then execute supported int32 graph operations node by node. Unsupported operations/types fail explicitly. Arithmetic is complete-word modulo 2^32; Task 2 has two length16 inputs and one scalar result.

Lean reads the actual Yosys FunctionalIR SMT transfer function, including its bitvector/memory sorts, declarations, single-binding lets, operations and record results. Give the imported program an explicit Lean evaluator. The main function is interpreted with caller-supplied state; the serializer's global main-initial assertions do not define this caller's state. Document that distinction and retain all permitted unknown register states and arbitrary input-memory words.

Approaches considered: rewrite all existing temporal proof automation in Lean; or prove the Lean-interpreted SMT transfer function agrees with the already checked circuit model, then transport the existing whole-transaction proof. Choose the latter as an implementation decision: it preserves the complete Task 2 claim and avoids rebuilding unrelated proof discovery. The parsed graph must likewise be proved to compute dot32. A runtime comparison alone cannot authorize the final theorem.

Acceptance: actual graph and SMT parse in Lean; numerical controls agree; parser/type/unsupported-operation mutations reject; a universal kernel-checked theorem links the new parsed/interpreted models under the same reset/ready/input-memory contract, with no extra axioms. Original PyTorch capture and Yosys RTL-to-SMT remain declared external boundaries. Parser implementation language alone is not claimed as a verified grammar-to-external-system theorem.
