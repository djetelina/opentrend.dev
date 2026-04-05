---
name: "Nix (nixpkgs)"
icon: "&#xf313;"
color: "#7ebae4"
source_url: "https://nixos.org/manual/nixpkgs/stable/#chap-quick-start"
build_env: "Any Linux or macOS with Nix installed"
tools: ["Nix package manager", "nixfmt-rfc-style (formatter)"]
requirements:
  - "Must build reproducibly"
  - "Must have a license"
  - "Add yourself as maintainer in maintainer-list.nix"
---

Nixpkgs is one of the largest package repositories in existence (~100k packages). Packages are Nix expressions — functional, reproducible build recipes. The community is very welcoming to new contributors. New packages go into the `pkgs/by-name/` directory using a convention-based structure.

## 1. Fork nixpkgs

Fork [nixpkgs](https://github.com/NixOS/nixpkgs) and clone it locally. Create a branch from `master`:

```bash
git clone https://github.com/youruser/nixpkgs.git
cd nixpkgs
git checkout -b yourpkg-init
```

## 2. Write a derivation

Create `pkgs/by-name/yo/yourpkg/package.nix` (first two letters of the package name as the subdirectory). Use the appropriate builder for your language:

**Go:**
```nix
{
  lib,
  buildGoModule,
  fetchFromGitHub,
}:

buildGoModule rec {
  pname = "yourpkg";
  version = "1.2.0";

  src = fetchFromGitHub {
    owner = "you";
    repo = "yourpkg";
    rev = "v${version}";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  vendorHash = "sha256-BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=";

  ldflags = [ "-s" "-w" "-X main.version=${version}" ];

  meta = {
    description = "Short description of your tool";
    homepage = "https://github.com/you/yourpkg";
    changelog = "https://github.com/you/yourpkg/releases/tag/v${version}";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ yourusername ];
    mainProgram = "yourpkg";
  };
}
```

**Rust:**
```nix
{
  lib,
  rustPlatform,
  fetchFromGitHub,
}:

rustPlatform.buildRustPackage rec {
  pname = "yourpkg";
  version = "1.2.0";

  src = fetchFromGitHub {
    owner = "you";
    repo = "yourpkg";
    rev = "v${version}";
    hash = "sha256-AAAA...=";
  };

  cargoHash = "sha256-BBBB...=";

  meta = {
    description = "Short description";
    homepage = "https://github.com/you/yourpkg";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ yourusername ];
  };
}
```

**Python:**
```nix
{
  lib,
  python3Packages,
  fetchFromGitHub,
}:

python3Packages.buildPythonApplication rec {
  pname = "yourpkg";
  version = "1.2.0";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "you";
    repo = "yourpkg";
    rev = "v${version}";
    hash = "sha256-AAAA...=";
  };

  build-system = with python3Packages; [ setuptools ];
  dependencies = with python3Packages; [ click requests ];

  meta = {
    description = "Short description";
    homepage = "https://github.com/you/yourpkg";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ yourusername ];
  };
}
```

**Tip:** Use `nix-prefetch-github you yourpkg --rev v1.2.0` to get the correct `hash`, and leave `vendorHash`/`cargoHash` empty on first build — the error message will tell you the correct hash.

## 3. Test it

```bash
nix-build -A yourpkg
./result/bin/yourpkg --version

# Format the file
nix-shell -p nixfmt-rfc-style --run 'nixfmt pkgs/by-name/yo/yourpkg/package.nix'
```

## 4. Submit a PR

Commit with the message format `yourpkg: init at 1.2.0` and open a PR to nixpkgs. Add yourself as a maintainer in `maintainers/maintainer-list.nix` if you're new.

The nixpkgs CI (ofborg) will automatically build-test your package on Linux and macOS. Expect reviews within a few days — the community is active and helpful.

**Tip:** For updates, the commit message format is `yourpkg: 1.1.0 -> 1.2.0`.
