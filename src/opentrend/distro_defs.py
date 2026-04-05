"""Shared distro definitions used by both discovery and the distro collector."""

# Per-distro constants: repo lists, path templates ({name} = package name),
# and version-extraction regex patterns for distros that use raw file scraping.

ALPINE_REPOS = ["community", "main", "testing"]
ALPINE_VERSION_RE = r"^pkgver=(.+)$"

VOID_PATH = "srcpkgs/{name}/template"
VOID_VERSION_RE = r"^version=(.+)$"

TERMUX_PATH = "packages/{name}/build.sh"
TERMUX_VERSION_RE = r'^TERMUX_PKG_VERSION="?([^"\n]+)"?'

CHIMERA_SUBDIRS = ["main", "contrib", "user"]
CHIMERA_VERSION_RE = r'^pkgver\s*=\s*"([^"]+)"'

NIX_VERSION_RE = r'version\s*=\s*"([^"]+)"'

OPENBSD_CATEGORIES = [
    "sysutils",
    "devel",
    "www",
    "net",
    "security",
    "textproc",
    "lang",
    "databases",
    "misc",
    "productivity",
]
OPENBSD_VERSION_PATTERNS = [
    r"^MODGO_VERSION\s*=\s*v?(.+)$",
    r"^V\s*=\s*(.+)$",
    r"^DISTNAME\s*=\s*\S+-v?([0-9][0-9.]+)",
    r"^GH_TAGNAME\s*=\s*v?(.+)$",
]

FREEBSD_CATEGORIES = [
    "sysutils",
    "devel",
    "www",
    "net",
    "security",
    "textproc",
    "lang",
    "databases",
    "misc",
    "net-mgmt",
    "www-apps",
]
FREEBSD_VERSION_RE = r"^(?:PORTVERSION|DISTVERSION)=\s*(.+)$"

SLACKBUILDS_CATEGORIES = [
    "system",
    "network",
    "development",
    "misc",
    "audio",
    "desktop",
    "games",
    "graphics",
    "libraries",
    "multimedia",
    "office",
    "perl",
    "python",
    "ruby",
    "academic",
    "accessibility",
    "ham",
    "haskell",
    "gis",
]
SLACKBUILDS_VERSION_RE = r'^VERSION="([^"]+)"'

WAKEMEOPS_CATEGORIES = ["devops", "sysadmin", "network", "development", "misc"]
WAKEMEOPS_VERSION_RE = r"^\s+-\s+([0-9][0-9.]+)"

SCOOP_BUCKETS = ["main", "extras"]
