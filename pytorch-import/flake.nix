{
  description = "Import the Task 2 PyTorch graph into TorchLean";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/6fd329b2adfecb86ae49c1cba89689bd0f229e04";

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; config.cudaSupport = false; };
    python = pkgs.python3.withPackages (ps: [ ps.torch ps.numpy ]);
    lean = pkgs.lean4;
    tools = [ lean python pkgs.bash pkgs.coreutils pkgs.gitMinimal pkgs.curl pkgs.gnutar pkgs.gzip
      pkgs.zstd pkgs.unzip pkgs.stdenv.cc ];
    environment = {
      PYTHONNOUSERSITE = "1";
      SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
      GIT_SSL_CAINFO = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
      CURL_CA_BUNDLE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
      CC = "${pkgs.stdenv.cc}/bin/cc";
      CXX = "${pkgs.stdenv.cc}/bin/c++";
    };
    source = pkgs.lib.cleanSourceWith {
      src = self;
      filter = path: _: !builtins.elem (baseNameOf path)
        [ ".lake" "build" "__pycache__" ".git" "result" ];
    };
    dependencyKey = builtins.substring 0 16 (builtins.hashString "sha256"
      (builtins.readFile ./lake-manifest.json + builtins.readFile ./lean-toolchain + toString lean));
    runner = pkgs.writeShellApplication {
      name = "pytorch-import";
      runtimeInputs = tools;
      runtimeEnv = environment;
      text = ''
        cache_root="''${XDG_CACHE_HOME:-$HOME/.cache}"
        work="$cache_root/pytorch-import/${dependencyKey}"
        mkdir -p "$work"
        cp -rf ${source}/. "$work/"
        chmod u+w "$work"/*
        printf 'Working directory: %s\n' "$work"
        bash "$work/run.sh"
      '';
    };
  in {
    packages.${system} = { inherit lean python; default = runner; };
    apps.${system}.default = {
      type = "app";
      program = "${runner}/bin/pytorch-import";
      meta.description = "Export a PyTorch graph and import it into TorchLean";
    };
    devShells.${system}.default = pkgs.mkShellNoCC (environment // {
      packages = tools;
    });
  };
}
