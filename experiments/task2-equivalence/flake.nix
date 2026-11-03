{
  description = "Task 2 verification tools; compiler baseline supplied by LLM2FPGA";
  inputs.task2.url = "git+file:///home/roland/LLM2FPGA?rev=b6dc8abcc023e241016a1fe19564b0d5af0c25b4";
  inputs.nixpkgs.follows = "task2/nixpkgs";
  inputs.hardware-importer = {
    url = "github:ErosSph/xiangshan2Lean/a1299b564831e571b9b80f816219ae06c91db342";
    flake = false;
  };
  # Existing immutable, ABI-matched verification frontend on this Task 2 host.
  # Retain its Nix closure when moving the experiment to another machine.
  inputs.verification-yosys = {
    url = "path:/nix/store/0j9h5572kfzlqpbds1y9dja1p159ihfk-yosys-with-plugins-0.66";
    flake = false;
  };
  outputs = inputs@{ self, nixpkgs, task2, ... }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    lean435 = pkgs.stdenvNoCC.mkDerivation {
      pname = "lean";
      version = "4.35.0";
      src = builtins.fetchTarball {
        url = "https://github.com/leanprover/lean4/releases/download/v4.35.0/lean-4.35.0-linux.tar.zst";
        sha256 = "sha256-MPu+/p9dJgSEA0qHocgrdAv1TSMDSJ7gHPjrF9H3VlI=";
      };
      nativeBuildInputs = [ pkgs.patchelf ];
      buildInputs = [ pkgs.stdenv.cc.cc.lib ];
      dontConfigure = true;
      dontBuild = true;
      dontStrip = true;
      installPhase = ''
        mkdir -p "$out"
        cp -a . "$out/"
        chmod -R u+w "$out"
        for binary in "$out"/bin/* "$out"/lib/*.so* "$out"/lib/lean/*.so*; do
          if old_rpath=$(patchelf --print-rpath "$binary" 2>/dev/null); then
            patchelf --set-rpath "$old_rpath:${pkgs.lib.makeLibraryPath [ pkgs.glibc pkgs.stdenv.cc.cc.lib ]}" "$binary"
            if patchelf --print-interpreter "$binary" >/dev/null 2>&1; then
              patchelf --set-interpreter "${pkgs.stdenv.cc.bintools.dynamicLinker}" "$binary"
            fi
          fi
        done
      '';
    };
    verificationTools = pkgs.runCommand "task2-verification-tools" {} ''
      mkdir -p "$out"
      ln -s ${inputs.verification-yosys}/bin "$out/bin"
    '';
  in {
    packages.${system}.lean = lean435;
    devShells.${system}.default = pkgs.mkShellNoCC {
      packages = [ pkgs.python3 pkgs.gitMinimal pkgs.stdenv.cc lean435 verificationTools ];
      shellHook = ''
        export XDG_CACHE_HOME="$PWD/build/cache"
        export TASK2_HARDWARE_IMPORTER="${inputs.hardware-importer}"
      '';
    };
  };
}
