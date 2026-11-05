# Import the Task 2 PyTorch model into TorchLean

Start with **[Import.lean](Import.lean)**. The actual import is:

```lean
let program : NN.IR.Program ← IO.ofExcept (Import.IR.parseProgram artifact)
```

This calls TorchLean's own importer and validates the graph's shapes and element
types. The result is an ordinary TorchLean `NN.IR.Program`, printed for inspection.

Read the files in this order:

1. [model.py](model.py): the original Task 2 matrix multiplication model.
2. [export.py](export.py): export its two length-16 int32 inputs to
   [model.json](model.json), using TorchLean's upstream exporter.
3. [Import.lean](Import.lean): read that JSON and import it into TorchLean.

Run from this folder on x86_64 Linux with Nix flakes enabled:

```sh
nix run path:.
```

The directory can be copied on its own. `flake.nix` and `flake.lock` pin the Nix
environment (the unmodified nixpkgs `lean4` package, CPU PyTorch and NumPy).
The current nixpkgs pin provides Lean 4.28.0. `lakefile.lean` and
`lake-manifest.json` pin TorchLean and all Lean dependencies. There are no local
repository inputs or hardcoded Nix-store paths.

The Lean dependencies and `lean-toolchain` still target Lean 4.35.0. The Nix
environment runs the packaged compiler directly; the release's Mathlib cache
does not match it, and the dependencies may need changes for that compiler.

The locked environment provides Python 3.13.12, PyTorch 2.10.0 and NumPy 2.4.2.

The first run needs internet access to fetch the Nix packages and pinned Lean
dependencies. `run.sh` fetches the release's Mathlib cache before compiling
TorchLean's import modules, subject to the compiler compatibility issue above.
Later runs reuse that work under `$XDG_CACHE_HOME/pytorch-import` (default
`~/.cache/pytorch-import`), with a separate cache directory for each Lean package.
The command prints the working directory and the imported `NN.IR.Program`.

For editing the example directly, use:

```sh
nix develop path:. --command bash run.sh
```

`EmitExporter.lean` writes the upstream Python exporter into the ignored `build/`
directory. `export.py` regenerates `model.json`; `Import.lean` reads it fresh.

Before switching to the nixpkgs compiler, reproduction with Lean 4.35.0 was
checked from an independent copy, with no borrowed Lean caches and no host tools
on `PATH`. All 16 Lean dependencies were checked out at their locked revisions.
A cached rerun with network access disabled also passed and
produced the same `model.json` byte for byte.

Scope: graph import and shape/type validation. There is no hardware, SMT,
equivalence proof or custom integer interpreter in this folder. Execution of
int32 matrix multiplication is a separate limitation of the pinned upstream
reference interpreter; importing the typed graph works independently of it.
