---
name: "GNU Guix"
icon: "&#xf17c;"
color: ""
source_url: "https://guix.gnu.org/manual/en/html_node/Packaging-Guidelines.html"
build_env: "Any Linux with Guix installed"
tools: ["GNU Guix"]
requirements:
  - "Must be free software (FSF-approved license only)"
  - "Must build reproducibly"
  - "Submitted via mailing list"
---

GNU Guix is a functional package manager (and full Linux distribution) that uses GNU Guile Scheme for package definitions. Every package is a reproducible build recipe — no global state, no side effects. Guix has strong free software principles and a welcoming community. Packages are submitted via patches to the `guix-patches` mailing list.

## 1. Set up a development environment

Clone the Guix repository and build the development environment:

```bash
git clone https://git.savannah.gnu.org/git/guix.git
cd guix
guix shell -D guix
./bootstrap
./configure --localstatedir=/var
```

## 2. Write a package definition

Package definitions live in `gnu/packages/`. Find the appropriate module for your tool (e.g., `golang.scm` for Go tools) and add your definition:

```scheme
(define-public yourpkg
  (package
    (name "yourpkg")
    (version "1.2.0")
    (source
     (origin
       (method git-fetch)
       (uri (git-reference
             (url "https://github.com/you/yourpkg")
             (commit (string-append "v" version))))
       (file-name (git-file-name name version))
       (sha256
        (base32 "0aaa...your-hash-here..."))))
    (build-system go-build-system)
    (arguments
     (list
      #:import-path "github.com/you/yourpkg"
      #:install-source? #f))
    (home-page "https://github.com/you/yourpkg")
    (synopsis "Short one-line description")
    (description
     "Longer description of what your tool does.  This can span
multiple lines and should explain the purpose and key features.")
    (license license:expat)))  ;; MIT is called "expat" in Guix
```

Guix provides build systems for many languages: `go-build-system`, `cargo-build-system`, `python-build-system`, `node-build-system`, etc. Each handles dependency fetching and compilation automatically.

## 3. Build and test

```bash
# Build the package
guix build yourpkg

# Run it from the store
guix shell yourpkg -- yourpkg --version

# Lint the definition
guix lint yourpkg

# Check reproducibility
guix build yourpkg --check
```

The `guix lint` command verifies formatting, checks URLs, and validates the description. Fix any warnings before submitting.

## 4. Submit via the mailing list

Guix uses a patch-based workflow through the GNU mailing lists, not GitHub PRs:

```bash
git add gnu/packages/yourmodule.scm
git commit -m "gnu: Add yourpkg."
git format-patch -1
# Send the patch to guix-patches@gnu.org
```

Use `git send-email` or attach the patch to an email to `guix-patches@gnu.org`. The patch tracker is at [issues.guix.gnu.org](https://issues.guix.gnu.org/). Reviewers will test your package and may suggest changes.

Follow the commit message convention: `gnu: Add yourpkg.` for new packages, `gnu: yourpkg: Update to 1.3.0.` for version bumps.

**Tip:** For faster iteration, use a [channel](https://guix.gnu.org/manual/en/html_node/Channels.html) — your own Guix package repository that users can add alongside the official one, similar to a Homebrew tap.
