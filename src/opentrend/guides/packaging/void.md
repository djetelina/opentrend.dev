---
name: "Void Linux"
icon: "&#xf17c;"
color: "#478061"
source_url: "https://github.com/void-linux/void-packages/blob/master/CONTRIBUTING.md"
build_env: "Any Linux via Docker (xbps-src)"
tools: ["xbps-src (from void-packages repo)"]
requirements:
  - "Must not duplicate an existing package"
  - "Must build with xbps-src"
  - "No proprietary software"
---

Void Linux uses XBPS as its package manager and `xbps-src` as the build system. Packages are defined as Bash template files in the [void-packages](https://github.com/void-linux/void-packages) repository. Void supports both glibc and musl libc, and packages must build on both. The community is selective but fair — useful, well-maintained tools are welcome.

## 1. Set up the build environment

Clone void-packages and bootstrap the build chroot:

```bash
git clone https://github.com/void-linux/void-packages.git
cd void-packages
./xbps-src binary-bootstrap
```

## 2. Create a template

Templates live in `srcpkgs/yourpkg/template`. Create the directory and write the template file:

```bash
# srcpkgs/yourpkg/template
pkgname=yourpkg
version=1.2.0
revision=1
build_style=go
go_import_path=github.com/you/yourpkg
short_desc="Short description of your tool"
maintainer="Your Name <you@example.com>"
license="MIT"
homepage="https://github.com/you/yourpkg"
distfiles="https://github.com/you/yourpkg/archive/v${version}.tar.gz"
checksum=abc123def456...
```

Void provides many `build_style` options that handle language-specific builds automatically:

- **go** — sets up GOPATH, runs `go build`
- **cargo** — runs `cargo build --release`
- **python3-pep517** — builds Python packages with PEP 517
- **cmake** / **meson** / **gnu-configure** — for C/C++ projects

For binary releases where no compilation is needed, use `build_style=void` and define `do_install()` manually:

```bash
pkgname=yourpkg-bin
version=1.2.0
revision=1
build_style=void
short_desc="Short description of your tool (prebuilt binary)"
maintainer="Your Name <you@example.com>"
license="MIT"
homepage="https://github.com/you/yourpkg"
distfiles="https://github.com/you/yourpkg/releases/download/v${version}/yourpkg-linux-${XBPS_TARGET_MACHINE}.tar.gz"
checksum=abc123...

do_install() {
    vbin yourpkg
    vlicense LICENSE
}
```

Helper functions like `vbin`, `vman`, `vlicense`, and `vdoc` install files to the correct locations automatically.

## 3. Build and test

```bash
./xbps-src pkg yourpkg
# Install locally to verify
xi yourpkg
yourpkg --version
```

Run `xlint srcpkgs/yourpkg/template` to check for common issues before submitting.

## 4. Submit a pull request

Fork void-packages, commit your template, and open a PR. Follow the commit message convention:

```
New package: yourpkg-1.2.0
```

CI will automatically build your package on x86_64, i686, aarch64, and armv7l for both glibc and musl. All builds must succeed. Maintainers review PRs regularly — expect feedback within a week.

**Tip:** For version updates, the commit message format is `yourpkg: update to 1.3.0`. Keep the template minimal — avoid custom `do_build()` or `do_install()` overrides when a `build_style` handles things correctly.
