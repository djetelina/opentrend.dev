---
name: "Scoop"
icon: "&#xe70f;"
color: "#9b59b6"
source_url: "https://github.com/ScoopInstaller/Scoop/wiki/App-Manifests"
build_env: "Windows only (JSON manifest, no build step)"
tools: ["Scoop (for testing)"]
requirements:
  - "Must be a Windows CLI tool"
  - "Must have a stable release URL"
  - "No GUI-only apps in Main bucket (use Extras)"
  - "Must have a checksum"
---

Scoop is a command-line installer for Windows that focuses on developer tools. Unlike Chocolatey, packages are simple JSON manifests with no install scripts — Scoop handles extraction and PATH management. Manifests live in "buckets" (Git repos), and the two official ones are **Main** (popular CLI tools) and **Extras** (GUI apps and less common tools).

## 1. Write a manifest

Create a JSON file named `yourpkg.json`. The manifest describes where to download the binary, how to verify it, and how to expose it:

```json
{
    "version": "1.2.0",
    "description": "Short description of your tool",
    "homepage": "https://github.com/you/yourpkg",
    "license": "MIT",
    "architecture": {
        "64bit": {
            "url": "https://github.com/you/yourpkg/releases/download/v1.2.0/yourpkg-windows-amd64.zip",
            "hash": "abc123..."
        },
        "arm64": {
            "url": "https://github.com/you/yourpkg/releases/download/v1.2.0/yourpkg-windows-arm64.zip",
            "hash": "def456..."
        }
    },
    "bin": "yourpkg.exe",
    "checkver": "github",
    "autoupdate": {
        "architecture": {
            "64bit": {
                "url": "https://github.com/you/yourpkg/releases/download/v$version/yourpkg-windows-amd64.zip"
            },
            "arm64": {
                "url": "https://github.com/you/yourpkg/releases/download/v$version/yourpkg-windows-arm64.zip"
            }
        },
        "hash": {
            "url": "$url.sha256"
        }
    }
}
```

Key fields: `bin` tells Scoop which executable to shim onto PATH. `checkver` with `"github"` automatically detects new releases from the GitHub API. The `autoupdate` block defines URL templates for automated version bumps.

## 2. Test locally

Install directly from your manifest file:

```powershell
scoop install .\yourpkg.json
yourpkg --version
scoop uninstall yourpkg
```

## 3. Submit to a bucket

For the **Main** bucket (CLI developer tools with broad appeal), fork [ScoopInstaller/Main](https://github.com/ScoopInstaller/Main) and add your manifest to the `bucket/` directory. For **Extras** (everything else), use [ScoopInstaller/Extras](https://github.com/ScoopInstaller/Extras).

Requirements for Main:
- Must be a CLI tool or developer utility
- Must have a stable release (no pre-release only)
- Must not require admin privileges

Open a PR with your manifest. Scoop maintainers typically review within a few days.

## 4. Use your own bucket

If you prefer not to wait for review or your tool doesn't fit the official buckets, create your own bucket — it's just a Git repo with JSON manifests:

```bash
gh repo create scoop-yourpkg --public
# Add yourpkg.json to the bucket/ directory (or repo root)
```

Users add it with:

```powershell
scoop bucket add yourpkg https://github.com/you/scoop-yourpkg
scoop install yourpkg
```

**Tip:** Scoop's `autoupdate` and `checkver` system is powerful. Run `scoop checkup` on your manifests periodically to verify they stay valid, or use the [Excavator](https://github.com/ScoopInstaller/Excavator) GitHub Action to auto-update manifests in your bucket.
