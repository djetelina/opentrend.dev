---
name: "Gentoo"
icon: "&#xf30d;"
color: "#54487a"
source_url: "https://wiki.gentoo.org/wiki/Ebuild_repository"
build_env: "Gentoo (or Gentoo container)"
tools: ["pip install pkgdev pkgcheck (or app-portage/* on Gentoo)"]
requirements:
  - "Must follow Gentoo QA policy"
  - "Ebuild must pass repoman/pkgcheck"
  - "Can use personal overlay for faster iteration"
---

Gentoo is a source-based distribution where packages are built from ebuilds — Bash scripts that define how to fetch, configure, compile, and install software. Gentoo's Portage tree is one of the largest repositories available. For new packages, the easiest path is through an overlay (third-party ebuild repository), with optional promotion to the official `::gentoo` tree.

## 1. Create an overlay

An overlay is your own ebuild repository. Create one for development and testing:

```bash
mkdir -p /var/db/repos/myoverlay/{metadata,profiles}
echo "myoverlay" > /var/db/repos/myoverlay/profiles/repo_name
cat > /var/db/repos/myoverlay/metadata/layout.conf <<'EOF'
masters = gentoo
auto-sync = false
EOF
```

Register it in `/etc/portage/repos.conf/myoverlay.conf`:

```ini
[myoverlay]
location = /var/db/repos/myoverlay
```

## 2. Write an ebuild

Ebuilds follow a strict directory structure: `category/package/package-version.ebuild`. The filename encodes the version:

```bash
# app-misc/yourpkg/yourpkg-1.2.0.ebuild
EAPI=8

DESCRIPTION="Short description of your tool"
HOMEPAGE="https://github.com/you/yourpkg"
SRC_URI="https://github.com/you/yourpkg/archive/v${PV}.tar.gz -> ${P}.tar.gz"

LICENSE="MIT"
SLOT="0"
KEYWORDS="~amd64 ~arm64"

BDEPEND="dev-lang/go"

src_compile() {
	ego build -trimpath -ldflags "-s -w -X main.version=${PV}" -o "${PN}" .
}

src_install() {
	dobin "${PN}"
	dodoc README.md
}
```

Key concepts: `EAPI=8` is the current ebuild API version. `SLOT="0"` means only one version can be installed. `KEYWORDS` with `~` prefix means the package is in testing (unstable). `ego` is a Gentoo wrapper for `go` that sets up the environment correctly.

Gentoo uses **eclasses** — shared libraries of build logic. For Go packages, inherit `go-module`:

```bash
EAPI=8
inherit go-module

# go-module handles vendoring and build automatically
EGO_SUM=(
	"github.com/some/dep v1.0.0"
	"github.com/some/dep v1.0.0/go.mod"
)
go-module_set_globals
```

## 3. Generate the manifest and test

```bash
cd /var/db/repos/myoverlay/app-misc/yourpkg
ebuild yourpkg-1.2.0.ebuild manifest    # Generate checksums
emerge --ask app-misc/yourpkg::myoverlay
pkgcheck scan                             # Lint the ebuild
```

## 4. Submit to ::gentoo

To get your package into the official tree, file a [package request bug](https://bugs.gentoo.org/) with the component `Ebuild Requests`. Attach your ebuild or reference your overlay. A Gentoo developer will review it, potentially suggest changes, and commit it to the tree.

Alternatively, publish your overlay on [overlays.gentoo.org](https://overlays.gentoo.org/) so users can add it via `eselect repository` and sync with `emerge --sync`.

**Tip:** Use `repoman` or `pkgcheck` to validate your ebuilds before submitting. Gentoo is very strict about QA — proper metadata, correct dependencies, and working test phases (`src_test`) make the review much smoother.
