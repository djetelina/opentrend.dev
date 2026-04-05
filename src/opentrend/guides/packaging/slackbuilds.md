---
name: "SlackBuilds.org"
icon: "&#xf17c;"
color: "#5f4985"
source_url: "https://slackbuilds.org/howto/"
build_env: "Slackware or Slackware-based only"
tools: ["sbopkg or Slackware pkgtools"]
requirements:
  - "Must build on Slackware -current"
  - "Must include .info + README + slack-desc"
  - "One package per submission"
---

SlackBuilds.org (SBo) is a community repository of build scripts for Slackware Linux. Each package consists of three files: a `.SlackBuild` script, a `.info` metadata file, and a `slack-desc` description. Packages are submitted through a web form and reviewed by maintainers. SBo aims for simplicity — scripts are straightforward Bash with minimal magic.

## 1. Create the .info file

The `.info` file defines download URLs, checksums, and metadata. It's a simple shell-sourceable format:

```bash
PRGNAM="yourpkg"
VERSION="1.2.0"
HOMEPAGE="https://github.com/you/yourpkg"
DOWNLOAD="https://github.com/you/yourpkg/archive/v1.2.0/yourpkg-1.2.0.tar.gz"
MD5SUM="abc123def456..."
DOWNLOAD_x86_64=""
MD5SUM_x86_64=""
REQUIRES=""
MAINTAINER="Your Name"
EMAIL="you@example.com"
```

If the source is the same for all architectures, leave `DOWNLOAD_x86_64` and `MD5SUM_x86_64` empty. If you need architecture-specific sources, fill in both. The `REQUIRES` field lists other SBo packages your build depends on (space-separated).

## 2. Write the .SlackBuild script

The build script follows a strict template. SBo provides a [template](https://slackbuilds.org/templates/) — start from that and customize the build section:

```bash
#!/bin/bash
PRGNAM=yourpkg
VERSION=${VERSION:-1.2.0}
BUILD=${BUILD:-1}
TAG=${TAG:-_SBo}
PKGTYPE=${PKGTYPE:-tgz}

if [ -z "$ARCH" ]; then
  case "$( uname -m )" in
    i?86) ARCH=i586 ;;
    arm*) ARCH=arm ;;
       *) ARCH=$( uname -m ) ;;
  esac
fi

CWD=$(pwd)
TMP=${TMP:-/tmp/SBo}
PKG=$TMP/package-$PRGNAM
OUTPUT=${OUTPUT:-/tmp}

set -e

rm -rf $PKG
mkdir -p $TMP $PKG $OUTPUT
cd $TMP
rm -rf $PRGNAM-$VERSION
tar xvf $CWD/$PRGNAM-$VERSION.tar.gz
cd $PRGNAM-$VERSION
chown -R root:root .

# Build
export GOPATH="$TMP/go"
go build -trimpath -ldflags="-s -w" -o $PRGNAM .

# Install
install -D -m 0755 $PRGNAM $PKG/usr/bin/$PRGNAM
install -D -m 0644 LICENSE $PKG/usr/doc/$PRGNAM-$VERSION/LICENSE

mkdir -p $PKG/install
cat $CWD/slack-desc > $PKG/install/slack-desc

cd $PKG
/sbin/makepkg -l y -c n $OUTPUT/$PRGNAM-$VERSION-$ARCH-$BUILD$TAG.$PKGTYPE
```

## 3. Create slack-desc

The `slack-desc` file is a fixed-format description shown by Slackware's package tools. Each line must be exactly `pkgname: text`, with 11 description lines:

```
yourpkg: yourpkg (short description)
yourpkg:
yourpkg: Longer description of what your tool does. Keep each line
yourpkg: under 73 characters. This is displayed when users query
yourpkg: package information.
yourpkg:
yourpkg:
yourpkg:
yourpkg:
yourpkg: Homepage: https://github.com/you/yourpkg
yourpkg:
```

## 4. Submit to SlackBuilds.org

Package all three files into a tar archive and submit through the [web form](https://slackbuilds.org/submit/). Follow the naming convention: the directory and archive must match `PRGNAM`.

Before submitting, test the full build cycle on a clean Slackware system. The maintainers verify that scripts follow the template, build cleanly, and produce working packages.

**Tip:** SBo tracks Slackware release cycles. When a new Slackware version drops, you'll need to resubmit or confirm your build still works on the new release.
