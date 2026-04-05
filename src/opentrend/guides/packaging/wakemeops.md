---
name: "WakeMeOps"
icon: "&#xf17c;"
color: ""
source_url: "https://docs.wakemeops.com/contributing/"
build_env: "No build step (YAML definition only)"
requirements:
  - "Must be a DevOps/CLI tool with GitHub releases"
  - "Must have pre-built binaries for Linux"
---

WakeMeOps is an APT repository that packages popular DevOps and developer tools for Debian and Ubuntu. Instead of complex build scripts, packages are defined with simple YAML files that describe how to download and install pre-built binaries. It fills the gap between "download from GitHub releases" and "wait for official distro packaging" for tools like k9s, lazygit, just, and hundreds of others.

## 1. Understand the model

WakeMeOps doesn't compile from source. It takes pre-built release artifacts (usually from GitHub releases) and repackages them as `.deb` files. This means your project needs to publish Linux binaries — typically `linux-amd64` and `linux-arm64` tarballs or standalone executables in GitHub releases.

## 2. Write a package definition

Package definitions live in the `packages/` directory as YAML files. Create `packages/yourpkg.yaml`:

```yaml
name: yourpkg
description: Short description of your tool
homepage: https://github.com/you/yourpkg
github: you/yourpkg

version:
  github_releases: you/yourpkg
  filter: "^v"
  strip_prefix: "v"

architectures:
  amd64:
    url: "https://github.com/you/yourpkg/releases/download/v{{version}}/yourpkg_{{version}}_linux_amd64.tar.gz"
    sha256: auto
    extract:
      - yourpkg
  arm64:
    url: "https://github.com/you/yourpkg/releases/download/v{{version}}/yourpkg_{{version}}_linux_arm64.tar.gz"
    sha256: auto
    extract:
      - yourpkg

install:
  bin:
    - yourpkg
```

Key fields:
- **version.github_releases**: Automatically detects new releases from the GitHub API.
- **version.filter / strip_prefix**: Cleans up version tags (e.g., `v1.2.0` becomes `1.2.0`).
- **sha256: auto**: Checksums are computed automatically during the build process.
- **extract**: Lists which files to pull from the archive. For standalone binaries (not tarballs), omit this and use `binary: true` instead.
- **install.bin**: Files to install to `/usr/bin/`.

For tools that publish checksums alongside releases:

```yaml
architectures:
  amd64:
    url: "https://github.com/you/yourpkg/releases/download/v{{version}}/yourpkg_{{version}}_linux_amd64.tar.gz"
    sha256:
      url: "https://github.com/you/yourpkg/releases/download/v{{version}}/checksums.txt"
      pattern: "yourpkg_{{version}}_linux_amd64.tar.gz"
```

## 3. Test locally

WakeMeOps provides tooling to validate and build packages locally:

```bash
git clone https://github.com/upciti/wakemeops.git
cd wakemeops
# Validate the YAML
python -m wakemeops validate packages/yourpkg.yaml
# Build the .deb
python -m wakemeops build packages/yourpkg.yaml --version 1.2.0
```

## 4. Submit a pull request

Fork [upciti/wakemeops](https://github.com/upciti/wakemeops) and open a PR with your YAML definition. CI validates the schema and test-builds the package. The maintainers are focused on DevOps/developer tooling, so your package should fit that category.

Once merged, the package is automatically built for all tracked versions and published to the APT repository. Users install it with:

```bash
# One-time setup
curl -sSL https://raw.githubusercontent.com/upciti/wakemeops/main/assets/install.sh | sudo bash
# Install
sudo apt install yourpkg
```

**Tip:** WakeMeOps tracks multiple versions simultaneously, so users can pin to specific versions via APT. Make sure your GitHub release naming is consistent — the version detection relies on predictable URL patterns.
