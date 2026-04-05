---
name: "Termux"
icon: "&#xf489;"
color: ""
source_url: "https://github.com/termux/termux-packages/blob/master/CONTRIBUTING.md"
build_env: "Any Linux via Docker (cross-compile)"
tools: ["Docker"]
requirements:
  - "Must work in Android terminal environment (no root, no X11)"
  - "Must cross-compile for ARM/ARM64"
---

Termux is a terminal emulator and Linux environment for Android. It has its own package repository with over 2000 packages built for ARM and x86 Android devices. Packages are cross-compiled from Linux using a custom build system. The key difference from other distros is the non-standard prefix: everything lives under `$TERMUX_PREFIX` (`/data/data/com.termux/files/usr`) instead of `/usr`.

## 1. Set up the build environment

Clone the termux-packages repo and build using Docker (recommended — avoids polluting your host):

```bash
git clone https://github.com/termux/termux-packages.git
cd termux-packages
./scripts/run-docker.sh
# Inside the container:
./build-package.sh -a aarch64 yourpkg
```

The Docker image contains the Android NDK, cross-compilation toolchains, and all necessary build infrastructure.

## 2. Write a build.sh

Create `packages/yourpkg/build.sh`. This is a Bash script with metadata variables and build functions:

```bash
TERMUX_PKG_HOMEPAGE=https://github.com/you/yourpkg
TERMUX_PKG_DESCRIPTION="Short description of your tool"
TERMUX_PKG_LICENSE="MIT"
TERMUX_PKG_MAINTAINER="@yourgithub"
TERMUX_PKG_VERSION="1.2.0"
TERMUX_PKG_SRCURL=https://github.com/you/yourpkg/archive/v${TERMUX_PKG_VERSION}.tar.gz
TERMUX_PKG_SHA256=abc123...
TERMUX_PKG_BUILD_IN_SRC=true
TERMUX_PKG_AUTO_UPDATE=true

termux_step_make() {
    termux_setup_golang
    export GOPATH=$TERMUX_PKG_BUILDDIR/_go
    go build -trimpath -ldflags "-s -w -X main.version=${TERMUX_PKG_VERSION}" -o yourpkg .
}

termux_step_make_install() {
    install -Dm700 yourpkg "${TERMUX_PREFIX}/bin/yourpkg"
}
```

Critical details for Termux packaging:

- **TERMUX_PREFIX**: Always use `$TERMUX_PREFIX` instead of `/usr`. Hardcoded paths like `/usr/bin`, `/etc`, or `/tmp` will break on Android.
- **Cross-compilation**: The build runs on x86_64 Linux but targets ARM/AArch64 Android. Go and Rust handle this well; C/C++ projects need the NDK toolchain.
- **No root**: Termux runs without root, so packages cannot write to system directories.
- **TERMUX_PKG_AUTO_UPDATE**: Set to `true` to enable automatic version tracking via GitHub releases.

## 3. Handle Termux-specific patches

Many projects need patches to work on Android. Common issues include hardcoded `/tmp` (use `$TERMUX_PREFIX/tmp`), missing `/proc` entries, and `inotify` limitations. Place patches in `packages/yourpkg/`:

```bash
# packages/yourpkg/fix-tmp-path.patch
--- a/config.go
+++ b/config.go
@@ -10,7 +10,7 @@
-    tmpDir := "/tmp"
+    tmpDir := os.TempDir()
```

Patches are applied automatically in alphabetical order before the build step.

## 4. Test on a device

After building, transfer the `.deb` to a Termux environment and install:

```bash
dpkg -i yourpkg_1.2.0_aarch64.deb
yourpkg --version
```

## 5. Submit a pull request

Open a PR to [termux/termux-packages](https://github.com/termux/termux-packages). CI builds the package for all supported architectures (aarch64, arm, i686, x86_64). Maintainers review for Android compatibility issues.

**Tip:** If your tool has no Android-specific concerns and builds with Go or Rust, the Termux build script is usually very simple. Most complexity comes from C/C++ projects that need NDK patches.
