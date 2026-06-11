import io

from PIL import Image

from opentrend import og

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _assert_card(data: bytes) -> None:
    assert data[:8] == _PNG_MAGIC
    img = Image.open(io.BytesIO(data))
    assert img.size == (og.WIDTH, og.HEIGHT) == (1200, 630)


def test_default_card_is_png() -> None:
    _assert_card(og.render_default_card())


def test_project_card_renders() -> None:
    _assert_card(
        og.render_project_card(
            display_name="cheznav",
            repo="djetelina/cheznav",
            reach=408,
            stars=2,
            downloads=273,
            packages=3,
            license="MIT",
            version="v0.1.1",
        )
    )


def test_project_card_handles_overflow_and_missing_fields() -> None:
    # Very long name + large numbers + no license/version must still render.
    _assert_card(
        og.render_project_card(
            display_name="a-really-long-project-name-" * 5,
            repo="org/" + "x" * 120,
            reach=1_234_567,
            stars=89_000,
            downloads=4_500_000,
            packages=32,
        )
    )


def test_format_number() -> None:
    assert og._format_number(999) == "999"
    assert og._format_number(1_500) == "1.5k"
    assert og._format_number(2_000_000) == "2.0M"


def test_fallback_card_is_png() -> None:
    _assert_card(og.render_fallback_card())


def test_render_or_fallback_returns_card_on_success() -> None:
    png, failed = og.render_or_fallback(og.render_default_card, label="default")
    assert failed is False
    _assert_card(png)


def test_render_or_fallback_recovers_from_render_error() -> None:
    def boom() -> bytes:
        raise RuntimeError("font missing")

    png, failed = og.render_or_fallback(boom, label="boom")
    # A render failure must still yield a valid PNG, not propagate (which would
    # surface as an HTML 500 under the image/png route).
    assert failed is True
    _assert_card(png)
