---
name: "Pacstall"
icon: "&#xf17c;"
color: ""
source_url: "https://github.com/pacstall/pacstall/wiki/Pacscript-101"
build_env: "Ubuntu/Debian only"
tools: ["Pacstall"]
requirements:
  - "Must target Ubuntu/Debian"
---

Pacstall is an AUR-inspired package manager for Ubuntu and Debian-based systems. Packages are defined by "pacscripts" — Bash scripts similar to PKGBUILDs. Pacstall supports multiple variants (`-deb`, `-git`, `-bin`, `-app`) and builds real `.deb` packages under the hood, integrating cleanly with APT.

## 1. Choose a variant

Pacstall uses naming suffixes to indicate how a package is built:

- **yourpkg** — builds from source release tarball
- **yourpkg-bin** — installs a pre-built binary (fastest for users)
- **yourpkg-git** — builds from the latest git HEAD
- **yourpkg-deb** — repackages an existing `.deb` file
- **yourpkg-app** — for AppImage/Flatpak/Snap repackaging

## 2. Write a pacscript

Create `packages/yourpkg/yourpkg.pacscript` (or the variant name). Here's a `-bin` variant that downloads a pre-built binary:

```bash
pkgname="yourpkg-bin"
gives="yourpkg"
pkgver="1.2.0"
pkgdesc="Short description of your tool"
repology=("project: yourpkg")
url="https://github.com/you/yourpkg"
arch=('amd64' 'arm64')
license=('MIT')
source=("https://github.com/you/yourpkg/releases/download/v${pkgver}/yourpkg-linux-${CARCH}.tar.gz")
sha256sums=('abc123...' 'def456...')

package() {
    install -Dm755 "yourpkg" "${pkgdir}/usr/bin/yourpkg"
    install -Dm644 "LICENSE" "${pkgdir}/usr/share/licenses/yourpkg/LICENSE"
}
```

And a source build variant:

```bash
pkgname="yourpkg"
pkgver="1.2.0"
pkgdesc="Short description of your tool"
url="https://github.com/you/yourpkg"
arch=('amd64' 'arm64')
license=('MIT')
makedepends=('golang')
source=("https://github.com/you/yourpkg/archive/v${pkgver}.tar.gz")
sha256sums=('abc123...')

build() {
    cd "${_archive}"
    go build -trimpath -ldflags "-s -w -X main.version=${pkgver}" -o yourpkg .
}

package() {
    cd "${_archive}"
    install -Dm755 "yourpkg" "${pkgdir}/usr/bin/yourpkg"
}
```

Key fields: `gives` defines the actual package name when it differs from `pkgname` (e.g., `yourpkg-bin` provides `yourpkg`). `CARCH` is automatically set to the system architecture. `repology` links the package to Repology tracking.

## 3. Test locally

```bash
# Install pacstall if needed
sudo bash -c "$(curl -fsSL https://pacstall.dev/q/install)"

# Test your pacscript
pacstall -Il ./yourpkg.pacscript
yourpkg --version
pacstall -R yourpkg
```

The `-Il` flag installs from a local pacscript file.

## 4. Submit to pacstall-programs

Fork [pacstall/pacstall-programs](https://github.com/pacstall/pacstall-programs) and add your pacscript:

```bash
mkdir -p packages/yourpkg-bin
cp yourpkg-bin.pacscript packages/yourpkg-bin/
```

Open a PR. The CI runs `pacstall -Pl` to lint your pacscript and attempts a test build. Maintainers are responsive and the review process is typically fast.

**Tip:** You can submit multiple variants in separate directories. The `-bin` variant is recommended as the primary since it provides the fastest install experience for users.
