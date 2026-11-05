# PyTorch → TorchLean

From this directory on x86_64 Linux:

```sh
nix build .#model -o model.json
nix develop
lake exe cache get
lake --old build NN.Runtime.IR
lake env lean --run Import.lean
```

[model.py](model.py) defines the model and its two length-16 int32 inputs.
Nix generates the upstream TorchLean exporter, then derives `model.json` from
that model. Generated files are ignored. Changing the model rebuilds the JSON.
[Import.lean](Import.lean) parses it into TorchLean's `NN.IR.Program`, checking
shapes and element types.

`flake.lock` pins nixpkgs, including unmodified Lean 4.35.0 and CPU PyTorch.
`lake-manifest.json` pins TorchLean and its Lean dependencies. The exporter's
content hash pins the generated Python; update it when updating TorchLean.
The first build fetches the locked sources and Mathlib cache.
The compiler binaries stay unchanged; a small wrapper supplies leantar 0.1.20
because nixpkgs' bundled 0.1.19 cannot read current Mathlib archives.

Count every tracked line, including hidden files and lock files:

```sh
git ls-files -z -- . | xargs -0 wc -l
```
