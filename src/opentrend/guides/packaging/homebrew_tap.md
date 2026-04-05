---
name: "Homebrew Tap"
icon: "&#xe711;"
color: "#fbb040"
source_url: "https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap"
build_env: "macOS or Linux"
tools: ["Homebrew"]
requirements:
  - "GitHub repo named homebrew-<name>"
---

A Homebrew Tap is your own formula repository — a GitHub repo that Homebrew can install from directly. Unlike `homebrew-core`, there's no review process, no notability requirement, and you control the release cadence. Users install with `brew install you/tap/yourpkg`. This is the best option for projects that don't meet homebrew-core's strict criteria or when you want full control over distribution.

## 1. Create the tap repository

Create a GitHub repository named `homebrew-tap` (the `homebrew-` prefix is required). This is what lets users refer to it as `you/tap`:

```bash
gh repo create homebrew-tap --public
git clone https://github.com/you/homebrew-tap.git
cd homebrew-tap
mkdir Formula
```

## 2. Write a formula with platform-specific binaries

Instead of building from source, you can distribute pre-built binaries for each platform. This is faster for users and avoids build dependencies:

```ruby
class Yourpkg < Formula
  desc "Short description of your tool"
  homepage "https://github.com/you/yourpkg"
  version "1.2.0"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/you/yourpkg/releases/download/v1.2.0/yourpkg-darwin-arm64.tar.gz"
      sha256 "aaa111..."
    end
    on_intel do
      url "https://github.com/you/yourpkg/releases/download/v1.2.0/yourpkg-darwin-amd64.tar.gz"
      sha256 "bbb222..."
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/you/yourpkg/releases/download/v1.2.0/yourpkg-linux-arm64.tar.gz"
      sha256 "ccc333..."
    end
    on_intel do
      url "https://github.com/you/yourpkg/releases/download/v1.2.0/yourpkg-linux-amd64.tar.gz"
      sha256 "ddd444..."
    end
  end

  def install
    bin.install "yourpkg"
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/yourpkg --version")
  end
end
```

## 3. Automate releases with GitHub Actions

Add a workflow that updates the formula whenever you create a new GitHub release. This eliminates manual maintenance:

```yaml
name: Update Homebrew Formula
on:
  release:
    types: [published]

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          repository: you/homebrew-tap
          token: ${{ secrets.TAP_GITHUB_TOKEN }}

      - name: Update formula
        run: |
          VERSION="${GITHUB_REF#refs/tags/v}"
          # Download each asset and compute sha256
          # Update Formula/yourpkg.rb with new version and hashes
          # Commit and push

      - name: Commit
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add Formula/yourpkg.rb
          git commit -m "yourpkg ${VERSION}"
          git push
```

Tools like [homebrew-releaser](https://github.com/Justintime50/homebrew-releaser) and GoReleaser's `brews` section can fully automate this step, generating the formula and pushing it to your tap on every release.

## 4. Install and share

Users add your tap once and then install normally:

```bash
brew tap you/tap
brew install yourpkg
# or in one command:
brew install you/tap/yourpkg
```

**Tip:** You can host multiple formulas in the same tap. If your project graduates to homebrew-core later, you can deprecate the tap formula and point users to the core version.
