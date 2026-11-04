# Lean Artifact Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Python exports graph data; Lean parses/interprets graph and hardware SMT and proves the Task 2 transaction equivalent.

**Architecture:** Native Lean artifact parsers and explicit evaluators, with a checked refinement to the existing full-circuit proof. One small entry point exposes imports and the final theorem. Preserve historical evidence.

**Tech Stack:** Existing pinned Lean4.35/TorchLean/Nix; Python only for PyTorch capture on the new path.

**Spec:** docs/superpowers/specs/2026-11-04-lean-artifact-flow-design.md

## Global Constraints

- Frozen Task2 inputs/RTL and historical proof bundles remain unchanged.
- Complete int32 words, arbitrary input memories and all permitted raw initial registers.
- Same four-reset-edge, fixed-ready, first-accepted-payload contract.
- No Python SMT parsing/model emission or assumed model equivalence on the new path.
- Unsupported syntax/operations/types fail explicitly. Standard Lean axioms only.

## Review Focus

1. Negative/overflow values retain complete words; graph execution is node based.
2. Malformed, ill-typed, unsupported or shadowed references reject rather than defaulting values.
3. SMT initialization assertions are distinguished from caller-supplied transfer-function state.
4. Numerical controls do not stand in for universal interpretation/refinement proofs.
5. The documented small entry point names real artifacts and cannot silently reuse stale imported models.

### Task 1: Lean graph import and integer evaluation

**Files:** LeanFlow/Graph.lean, LeanFlow/Tests.lean, LeanFlow/export.py.
**Interfaces:** Lean graph parse and eval over flat complete-word tensors; export emits JSON only.
- [x] RED: graph parse/eval controls and unsupported graph/type mutations.
- [x] Implement Lean parser using TorchLean validation and int32 node semantics; generic rank-one/matrix contraction using existing layout rules.
- [x] GREEN: controls and a theorem for the actual parsed Task2 graph against dot32.

### Task 2: Lean SMT parser and evaluator

**Files:** LeanFlow/SMT.lean and SMT tests.
**Interfaces:** parse : String → Except String Program; eval : Program → inputs → state → Except String result.
- [x] RED: bitvector operations, signed shifts/comparisons, memory select/store, let bindings, invalid sorts/references and unsupported syntax.
- [x] Implement native S-expression parsing, strict typed lowering and explicit value semantics.
- [x] GREEN: parse and execute the actual full SMT artifact; compare complete transition/output controls with existing circuit model.

### Task 3: Universal refinement and observable equivalence

**Files:** LeanFlow/Import.lean, LeanFlow/Equivalence.lean and generated Lean-only proof certificates if needed.
**Interfaces:** parsed graph/SMT constants; universal transfer refinement; final Implements theorem.
- [x] RED: missing refinement/final theorem and corrupted-operator rejection.
- [x] Prove semantic agreement with the existing circuit for arbitrary inputs/state, then transport its reset/first-result proof and graph interpretation theorem.
- [x] GREEN: actual full Task2 theorem type/axiom audit; negative-control proof rejected.

### Task 4: Small entry point and validation

**Files:** LeanFlow/Main.lean, LeanFlow/README.md; minimal Lake wiring.
- [x] One clear export/read/prove command sequence; actual artifact paths visible in Lean.
- [x] Run native tests and final proof audits; retain concise evidence.
- [ ] Fresh final review and one TDD fix pass; preserve branch without publishing.
