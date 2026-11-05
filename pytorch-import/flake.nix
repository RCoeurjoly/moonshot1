{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/1d060086d60cb76a40cf37109f979d88a5bd6396";

  outputs = { nixpkgs, ... }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; config.cudaSupport = false; };
    python = pkgs.python3.withPackages (ps: [ ps.torch ps.numpy ]);
    leantar = pkgs.fetchzip {
      url = "https://github.com/digama0/leangz/releases/download/v0.1.20/leantar-v0.1.20-x86_64-unknown-linux-musl.tar.gz";
      hash = "sha256-dT9RPFD0MeJgkhf9q+KyHuiQimQ3XKzZiaDYyo7xgNY=";
      postFetch = ''mkdir -p "$out/bin"; mv "$out/leantar" "$out/bin/"'';
    };
    lean = pkgs.symlinkJoin {
      name = "lean4";
      paths = [ pkgs.lean4 ];
      postBuild = ''
        cp --remove-destination ${pkgs.lean4}/bin/.lean-wrapped "$out/bin/lean"
        cp --remove-destination ${pkgs.lean4}/bin/lake "$out/bin/lake"
        ln -sf ${leantar}/bin/leantar "$out/bin/leantar"
      '';
    };
    exporter = pkgs.runCommandCC "torchlean_export.py" {
      nativeBuildInputs = [ lean ] ++ (with pkgs; [ gitMinimal curl cacert ]);
      LEAN_NUM_THREADS = "2";
      outputHashMode = "flat";
      outputHash = "sha256-C4yjzI2IKpLeBe0dx1DsvW70bSSXghruMDmroQdNRWU=";
    } ''
      cp ${./lakefile.lean} lakefile.lean
      cp ${./lake-manifest.json} lake-manifest.json
      cp ${./lean-toolchain} lean-toolchain
      export MATHLIB_CACHE_DIR="$TMPDIR/mathlib-cache"
      lake exe cache get
      lake --old build NN.Runtime.PyTorch.Export.TorchExport
      cat > Emit.lean <<'LEAN'
      import NN.Runtime.PyTorch.Export.TorchExport
      def main : IO Unit := IO.print (Export.PyTorch.TorchExport.script {})
      LEAN
      lake env lean --run Emit.lean > "$out"
    '';
    model = pkgs.runCommand "model.json" { nativeBuildInputs = [ python ]; } ''
      cp ${./model.py} model.py
      cp ${exporter} torchlean_export.py
      python model.py "$out"
    '';
  in {
    packages.${system} = { inherit model; default = model; };
    devShells.${system}.default = pkgs.mkShell {
      inputsFrom = [ model exporter ];
      MATHLIB_CACHE_DIR = ".lake/cache";
    };
  };
}
