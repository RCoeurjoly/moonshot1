# PyTorch → TorchLean

```sh
nix develop
lake exe cache get
lake --old build NN.Runtime.IR
artifact=$(nix build .#model --no-link --print-out-paths)
lake env lean --run Import.lean "$artifact"
```

`model.py` → Nix-generated JSON → TorchLean's checked `NN.IR.Program` (x86_64 Linux).
TorchLean's pinned commit supplies its dependency lock.
Lake generates the local manifest; it is ignored.
Update the exporter hash when updating TorchLean.
The unchanged Lean 4.35.0 compiler uses leantar 0.1.20 to read the Mathlib cache.
Count tracked lines: `git ls-files -z -- . | xargs -0 wc -l`.
Lint: `nix develop --command statix check flake.nix` or `nix flake check .`.
