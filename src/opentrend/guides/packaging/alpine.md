---
name: "Alpine Linux"
icon: "&#xf300;"
color: "#0d597f"
source_url: "https://wiki.alpinelinux.org/wiki/Creating_an_Alpine_package"
build_env: "Any Linux via Docker (abuild)"
tools: ["alpine-sdk (available cross-distro, includes abuild)"]
requirements:
  - "Must build with abuild"
  - "New packages go to testing/ first"
  - "Must have a maintainer"
---

Alpine Linux is widely used in containers thanks to its tiny footprint and musl libc base. Packages are built with `abuild` from `APKBUILD` files — shell scripts that define sources, dependencies, and build steps. New packages start in the `testing/` repository and graduate to `community/` or `main/` after proving stability.

## 1. Set up the build environment

Install the build tools and generate a signing key:

```bash
apk add alpine-sdk
adduser $USER abuild
abuild-keygen -a -i
```

## 2. Write an APKBUILD

Create a directory for your package and write the `APKBUILD` file:

```bash
# testing/yourpkg/APKBUILD
pkgname=yourpkg
pkgver=1.2.0
pkgrel=0
pkgdesc="Short description of your tool"
url="https://github.com/you/yourpkg"
arch="all"
license="MIT"
makedepends="go"
source="$pkgname-$pkgver.tar.gz::https://github.com/you/yourpkg/archive/v$pkgver.tar.gz"
options="!check"  # Remove this once you add tests

build() {
	cd "$builddir"
	go build -trimpath -ldflags "-s -w -X main.version=$pkgver" -o yourpkg .
}

package() {
	cd "$builddir"
	install -Dm755 yourpkg "$pkgdir"/usr/bin/yourpkg
	install -Dm644 LICENSE "$pkgdir"/usr/share/licenses/$pkgname/LICENSE
}

sha512sums="
abc123...  yourpkg-1.2.0.tar.gz
"
```

Key conventions: Alpine uses `sha512sums` (not sha256). The `$builddir` variable points to the extracted source. The `arch` field should be `"all"` for most compiled software or `"noarch"` for scripts/interpreted languages.

For Go packages, Alpine provides the `go` build system that you can use instead of manual build steps:

```bash
makedepends="go"
source="..."

export GOFLAGS="-trimpath"

build() {
	go build -ldflags "-s -w" -o yourpkg .
}
```

## 3. Build and test

```bash
cd testing/yourpkg
abuild checksum    # Generate sha512sums
abuild -r          # Build the package
```

The `-r` flag installs missing dependencies automatically. The resulting `.apk` package ends up in `~/packages/`.

## 4. Submit to aports

Fork [alpinelinux/aports](https://gitlab.alpinelinux.org/alpine/aports) on Alpine's GitLab instance. New packages must go in `testing/`:

```bash
git add testing/yourpkg/APKBUILD
git commit -m "testing/yourpkg: new aport"
```

Open a merge request. Alpine's CI builds the package on all supported architectures. A maintainer reviews the APKBUILD — expect feedback on things like proper use of `install`, correct `depends` vs `makedepends` separation, and inclusion of a `check()` function for tests.

## 5. Graduate to community

After your package has been in `testing/` for a release cycle with no issues, you (or a maintainer) can move it to `community/`. This makes it available in Alpine's stable releases and official Docker images.

**Tip:** Run `apkbuild-lint APKBUILD` to catch style issues before submitting. Alpine is strict about security and minimal dependencies — avoid bundling or vendoring when system libraries are available.
