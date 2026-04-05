---
name: "Chocolatey"
icon: "&#xe70f;"
color: "#80b5e3"
source_url: "https://docs.chocolatey.org/en-us/create/create-packages"
build_env: "Windows only"
tools: ["Chocolatey", "NuGet CLI"]
requirements:
  - "Account on community.chocolatey.org"
  - "Package must pass automated review"
  - "Must not be malware"
  - "Installer must be silent-capable"
---

Chocolatey is the most widely used package manager for Windows. Packages are NuGet archives containing a `.nuspec` manifest and PowerShell install scripts. The community repository at [community.chocolatey.org](https://community.chocolatey.org/) goes through a moderation process before packages are publicly available, but the process is straightforward for well-structured packages.

## 1. Set up Chocolatey packaging

Install the Chocolatey CLI and create a package skeleton:

```powershell
choco new yourpkg
```

This generates a directory with template files: `yourpkg.nuspec`, `tools/chocolateyinstall.ps1`, and `tools/chocolateyuninstall.ps1`.

## 2. Define the .nuspec manifest

The `.nuspec` file contains package metadata — name, version, description, and dependencies:

```xml
<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2015/06/nuspec.xsd">
  <metadata>
    <id>yourpkg</id>
    <version>1.2.0</version>
    <title>YourPkg</title>
    <authors>Your Name</authors>
    <projectUrl>https://github.com/you/yourpkg</projectUrl>
    <licenseUrl>https://github.com/you/yourpkg/blob/main/LICENSE</licenseUrl>
    <requireLicenseAcceptance>false</requireLicenseAcceptance>
    <description>Short description of your tool. This is what shows on the community page.</description>
    <tags>cli developer-tools</tags>
    <projectSourceUrl>https://github.com/you/yourpkg</projectSourceUrl>
    <bugTrackerUrl>https://github.com/you/yourpkg/issues</bugTrackerUrl>
    <releaseNotes>https://github.com/you/yourpkg/releases/tag/v1.2.0</releaseNotes>
  </metadata>
</package>
```

## 3. Write the install script

The PowerShell install script downloads and places your binary. Use Chocolatey's built-in helpers for common patterns:

```powershell
# tools/chocolateyinstall.ps1
$ErrorActionPreference = 'Stop'

$toolsDir = "$(Split-Path -Parent $MyInvocation.MyCommand.Definition)"
$url64 = 'https://github.com/you/yourpkg/releases/download/v1.2.0/yourpkg-windows-amd64.zip'

$packageArgs = @{
  packageName   = $env:ChocolateyPackageName
  unzipLocation = $toolsDir
  url64bit      = $url64
  checksum64    = 'abc123...'
  checksumType64= 'sha256'
}

Install-ChocolateyZipPackage @packageArgs
```

Chocolatey automatically adds the `tools/` directory to PATH, so the extracted binary is immediately available. For `.exe` installers instead of zips, use `Install-ChocolateyPackage` with `silentArgs` for unattended installation.

## 4. Build and test locally

```powershell
choco pack
choco install yourpkg --source "." --force
yourpkg --version
choco uninstall yourpkg
```

## 5. Push to the community repository

Get an API key from your [Chocolatey account](https://community.chocolatey.org/account) and push:

```powershell
choco apikey --key YOUR_API_KEY --source https://push.chocolatey.org/
choco push yourpkg.1.2.0.nupkg --source https://push.chocolatey.org/
```

Packages enter a moderation queue where automated checks verify checksums, scan for viruses, and validate the install script. A human moderator then reviews the package. First submissions typically take 1-7 days. Subsequent version updates are faster, especially if the package has a clean history.

**Tip:** Use [AU (Automatic Updater)](https://github.com/majkinetor/au) to automate version bumps — it monitors your GitHub releases and submits updated packages to Chocolatey automatically.
