"""Tests for shared route helpers in routes/__init__.py."""

from opentrend.routes import parse_extra_packages, safe_redirect_url


class TestSafeRedirectUrl:
    def test_valid_relative_path(self) -> None:
        assert safe_redirect_url("/projects") == "/projects"

    def test_valid_nested_path(self) -> None:
        assert safe_redirect_url("/p/owner/repo") == "/p/owner/repo"

    def test_rejects_absolute_url(self) -> None:
        assert safe_redirect_url("https://evil.com/callback") == "/projects"

    def test_rejects_protocol_relative(self) -> None:
        assert safe_redirect_url("//evil.com") == "/projects"

    def test_rejects_path_traversal(self) -> None:
        assert safe_redirect_url("/../../etc/passwd") == "/projects"

    def test_rejects_empty_string(self) -> None:
        assert safe_redirect_url("") == "/projects"

    def test_custom_fallback(self) -> None:
        assert safe_redirect_url("", fallback="/home") == "/home"

    def test_rejects_javascript_scheme(self) -> None:
        assert safe_redirect_url("javascript:alert(1)") == "/projects"

    def test_allows_underscore_and_dot(self) -> None:
        assert safe_redirect_url("/p/my_repo/file.html") == "/p/my_repo/file.html"

    def test_rejects_backslash(self) -> None:
        assert safe_redirect_url("/foo\\bar") == "/projects"

    def test_allows_root(self) -> None:
        assert safe_redirect_url("/") == "/"


class TestParseExtraPackages:
    def _make_form(self, sources, names, taps=None):
        """Create a mock form object with getall()."""

        class MockForm:
            def __init__(self, data):
                self._data = data

            def getall(self, key):
                return self._data.get(key, [])

        data = {"extra_source[]": sources, "extra_name[]": names}
        if taps is not None:
            data["extra_tap[]"] = taps
        return MockForm(data)

    def test_normal_case(self) -> None:
        form = self._make_form(["pypi", "npm"], ["httpx", "axios"])
        result = parse_extra_packages(form)
        assert result == [
            {"source": "pypi", "package_name": "httpx"},
            {"source": "npm", "package_name": "axios"},
        ]

    def test_empty_values_skipped(self) -> None:
        form = self._make_form(["pypi", ""], ["httpx", ""])
        result = parse_extra_packages(form)
        assert len(result) == 1
        assert result[0]["package_name"] == "httpx"

    def test_homebrew_tap_prepends(self) -> None:
        form = self._make_form(["homebrew_tap"], ["myformula"], taps=["homebrew/core"])
        result = parse_extra_packages(form)
        assert result == [
            {"source": "homebrew_tap", "package_name": "homebrew/core/myformula"}
        ]

    def test_empty_form(self) -> None:
        form = self._make_form([], [])
        assert parse_extra_packages(form) == []

    def test_whitespace_stripped(self) -> None:
        form = self._make_form(["  pypi  "], ["  httpx  "])
        result = parse_extra_packages(form)
        assert result == [{"source": "pypi", "package_name": "httpx"}]
