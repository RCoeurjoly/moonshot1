# Retained opt-full evidence

The files in this directory describe the completed run. Fresh execution writes
new verdicts under `../build/`; the existing demos' retained reports are unchanged.

- [summary.json](summary.json): candidate universal correctness, 436-edge result,
  direct native refinement, test counts and preservation audit.
- [control-result.json](control-result.json): exact regenerated candidate,
  structural counts and all seven three-way controls.
- [universal-result.json](universal-result.json): all441 state and5 output
  checks, candidate correctness/first-result theorems and rejected mutation.
- [direct-result.json](direct-result.json): all451 baseline native state updates
  and5 outputs, arbitrary-length trace theorem, explicit state embedding,
  transitive dependency audits and both rejected native mutations.
- [comparison.json](comparison.json): one warm resource observation per path,
  generator/helper maintenance and measurement limits. No strict reduction in
  engineering effort is claimed; active engineering time was not measured.
- [full-run.log](full-run.log), [opt-tests.log](opt-tests.log),
  [baseline-tests.log](baseline-tests.log), [original-tests.log](original-tests.log):
  successful final commands and regression suites.
- [review.md](review.md): independent reviews and resolved findings.
- [preservation.json](preservation.json):202 pre-existing source/report identities.
- [evidence.json.gz](evidence.json.gz): named text sources, exact native models,
  generated obligations, traces, proof logs and hashes.

The direct theorem assumes states related by the documented embedding. Its
arbitrary input streams use the lifted native port interface. Neither this
refinement nor the concrete controls verify the RTL translators themselves.
