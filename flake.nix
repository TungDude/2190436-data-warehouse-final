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
          playwright
        ]);
      in {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.nodejs_22
            pkgs.terraform
            pkgs.awscli2
            pkgs.jq
          ];

          # Playwright: use Nix-built browser bundle so we don't need
          # `playwright install` and don't fight the dynamic linker.
          PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
          PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = "true";

          shellHook = ''
            # python3's nixpkgs setup hook exports LD_LIBRARY_PATH with
            # libs from this flake's nixpkgs, which collides with the
            # system glibc and breaks /run/current-system/sw/bin/ssh
            # (and therefore git push). Nix-installed py packages have
            # RPATHs baked in, so we don't need it at runtime.
            unset LD_LIBRARY_PATH

            VENV_DIR="$PWD/.venv"
            if [ ! -d "$VENV_DIR" ]; then
              echo "Creating Python venv..."
              python -m venv "$VENV_DIR" --system-site-packages
            fi
            source "$VENV_DIR/bin/activate"

            export PATH="$PWD/node_modules/.bin:$PATH"
          '';
        };
      });
}
