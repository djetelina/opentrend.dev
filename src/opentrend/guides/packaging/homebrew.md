---
name: "Homebrew"
icon: "&#xe711;"
color: "#fbb040"
source_url: "https://docs.brew.sh/Formula-Cookbook"
build_env: "macOS or Linux"
tools: ["Homebrew"]
requirements:
  - "75+ GitHub stars (or mass adoption)"
  - "Open source with a stable tagged release"
  - "Must be a CLI tool or utility (not a library)"
  - "Must not duplicate functionality of another formula"
  - "Must have a test block that verifies installation"
---

Homebrew is the most popular package manager for macOS (and Linux). Formulas are Ruby files that describe how to download and install software. Submitting to `homebrew-core` makes your tool available to millions of users via a simple `brew install`.

## 1. Create a formula

Generate a template from your release tarball:

```bash
brew create https://github.com/you/yourpkg/archive/v1.2.0.tar.gz
```

This creates a Ruby file in your local formula directory with the URL and SHA256 pre-filled.

## 2. Edit the formula

Fill in the metadata and build instructions. Homebrew has DSL helpers for common languages:

```ruby
class Yourpkg < Formula
  desc "Short description of your tool"
  homepage "https://github.com/you/yourpkg"
  url "https://github.com/you/yourpkg/archive/v1.2.0.tar.gz"
  sha256 "abc123..."
  license "MIT"
  head "https://github.com/you/yourpkg.git", branch: "main"

  depends_on "go" => :build

  def install
    system "go", "build", *std_go_args(ldflags: "-s -w")
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/yourpkg --version")
  end
end
```

**Language-specific helpers:**
- **Go:** Use `depends_on "go" => :build` and `std_go_args`
- **Rust:** Use `depends_on "rust" => :build` and `system "cargo", "install", *std_cargo_args`
- **Python:** Use `include Language::Python::Virtualenv` with `virtualenv_install_with_resources`
- **Node:** Use `depends_on "node"` and `system "npm", "install", *std_npm_args`

## 3. Test locally

```bash
brew install --build-from-source ./yourpkg.rb
brew test yourpkg
brew audit --strict --new yourpkg
```

The audit step catches common issues like missing test blocks, style violations, and incorrect metadata before you submit.

## 4. Submit a PR

Fork [homebrew-core](https://github.com/Homebrew/homebrew-core), add your formula to `Formula/y/yourpkg.rb` (first letter subdirectory), and open a pull request.

Read the [acceptable formulae](https://docs.brew.sh/Acceptable-Formulae) criteria first — Homebrew has strict requirements:
- Must be open source with a stable release
- Must have a test block
- Must not be a "library" (should have a binary or user-facing utility)
- Must be notable enough (GitHub stars, active development, etc.)

## 5. Auto-updates

Once merged, Homebrew's `brew livecheck` bot monitors your GitHub releases and auto-bumps the formula version via automated PRs. No manual maintenance needed for most projects — just keep making GitHub releases.

**Tip:** If your project doesn't meet homebrew-core criteria, consider a [Homebrew Tap](/guides/packaging/homebrew_tap) instead — your own formula repository with no review process.
