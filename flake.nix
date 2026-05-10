{
  description = "Dev shell for the data-warehouse-final project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };

        python = pkgs.python3.withPackages (ps: with ps; [
          pip
          setuptools
          wheel
          virtualenv
          pyyaml
          requests
          numpy
        ]);
      in {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.terraform
            pkgs.awscli2
            pkgs.jq
          ];

          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
            pkgs.stdenv.cc.cc.lib
            pkgs.zlib
            pkgs.libffi
            pkgs.openssl
          ];

          shellHook = ''
            VENV_DIR="$PWD/.venv"
            if [ ! -d "$VENV_DIR" ]; then
              echo "Creating Python venv..."
              python -m venv "$VENV_DIR" --system-site-packages
            fi
            source "$VENV_DIR/bin/activate"
          '';
        };
      });
}
