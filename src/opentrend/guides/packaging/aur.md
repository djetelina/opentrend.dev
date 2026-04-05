---
name: "AUR (Arch User Repository)"
icon: "&#xf303;"
color: "#1793d1"
source_url: "https://wiki.archlinux.org/title/AUR_submission_guidelines"
build_env: "Arch Linux (or Arch container)"
tools: ["pacman -S base-devel pacman-contrib"]
requirements:
  - "AUR account with SSH key"
  - "Must not duplicate an official Arch package"
  - "Must not be pre-built proprietary binaries (use -bin suffix for binary repackaging)"
---

The AUR is a community-driven repository for Arch Linux. Anyone can submit packages. Users install them via AUR helpers like `yay` or `paru`. Packages are defined by a `PKGBUILD` — a Bash script that tells `makepkg` how to fetch, build, and install your software.

## 1. Set up an AUR account

Register at [aur.archlinux.org](https://aur.archlinux.org/register) and add your SSH public key in account settings. You'll push packages via git over SSH.

## 2. Create a PKGBUILD

Write a `PKGBUILD` file that defines how to download, build, and install your package. The key variables are `pkgname`, `pkgver`, `source`, and the `build()` and `package()` functions. Use `makepkg` to test it locally before submitting.

```bash
# Maintainer: Your Name <you@example.com>
pkgname=yourpkg
pkgver=1.2.0
pkgrel=1
pkgdesc="Short description of your tool"
arch=('x86_64')
url="https://github.com/you/yourpkg"
license=('MIT')
depends=('glibc')
makedepends=('go')
source=("$pkgname-$pkgver.tar.gz::$url/archive/v$pkgver.tar.gz")
sha256sums=('SKIP')  # Replace with actual checksum

build() {
    cd "$pkgname-$pkgver"
    go build -o "$pkgname" .
}

package() {
    cd "$pkgname-$pkgver"
    install -Dm755 "$pkgname" "$pkgdir/usr/bin/$pkgname"
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
```

For binary releases (no compilation needed), you can create a `-bin` variant that just downloads and installs the pre-built binary:

```bash
pkgname=yourpkg-bin
pkgver=1.2.0
# ...
source=("$url/releases/download/v$pkgver/yourpkg-linux-amd64.tar.gz")

package() {
    install -Dm755 "$srcdir/yourpkg" "$pkgdir/usr/bin/yourpkg"
}
```

## 3. Generate .SRCINFO

Run `makepkg --printsrcinfo > .SRCINFO` to generate the metadata file required by the AUR. This must be committed alongside the PKGBUILD — the AUR web interface reads it to display package info.

## 4. Push to AUR

Clone the empty AUR git repo and push your files:

```bash
git clone ssh://aur@aur.archlinux.org/yourpkg.git
cd yourpkg
# Copy in your PKGBUILD and .SRCINFO
git add PKGBUILD .SRCINFO
git commit -m "Initial upload: yourpkg 1.2.0"
git push
```

Your package is immediately available on the AUR after pushing.

## 5. Maintain it

When you release a new version:

1. Update `pkgver` in the PKGBUILD
2. Update `sha256sums` (run `updpkgsums` if you have `pacman-contrib`)
3. Regenerate `.SRCINFO`
4. Commit and push

Consider also creating a `-git` variant that builds from your main branch — this tracks the latest development version and uses `pkgver()` to auto-detect the version from git tags.

**Tip:** Tools like [aurpublish](https://github.com/eli-schwartz/aurpublish) can automate publishing from a GitHub Actions workflow.
