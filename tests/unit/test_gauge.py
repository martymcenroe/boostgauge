"""Unit test suite for boostgauge.gauge facade.

Issue #1: Core gauge renderer — analog tachometer with arc, needle, and tick marks
"""

import sys
import pytest
from PIL import Image

from boostgauge.gauge import render, MIN_GAUGE_SIZE, DEFAULT_GAUGE_SIZE


def test_render_defaults() -> None:
    img = render(50.0)
    assert isinstance(img, Image.Image)
    assert img.size == (DEFAULT_GAUGE_SIZE, DEFAULT_GAUGE_SIZE)
    assert img.mode == "RGBA"


def test_render_no_tkinter_imports() -> None:
    render(50.0)
    imported_modules = set(sys.modules.keys())
    assert "tkinter" not in imported_modules
    assert "_tkinter" not in imported_modules


def test_value_type_validation() -> None:
    with pytest.raises(TypeError, match="Value must be a numeric float or int"):
        render("50.0")  # type: ignore

    with pytest.raises(TypeError, match="Value must be a numeric float or int"):
        render(None)  # type: ignore

    with pytest.raises(TypeError, match="Value must be a numeric float or int"):
        render(True)  # type: ignore


def test_value_clamping() -> None:
    img_under = render(-25.0)
    img_zero = render(0.0)
    assert img_under.tobytes() == img_zero.tobytes()

    img_over = render(150.0)
    img_max = render(100.0)
    assert img_over.tobytes() == img_max.tobytes()


def test_size_validation() -> None:
    img_custom = render(50.0, size=512)
    assert img_custom.size == (512, 512)

    with pytest.raises(ValueError, match="Gauge size must be an integer >= 128"):
        render(50.0, size=64)


def test_deterministic_output() -> None:
    img1 = render(42.0, telltales={"m1": 50.0}, size=256)
    img2 = render(42.0, telltales={"m1": 50.0}, size=256)
    assert img1.tobytes() == img2.tobytes()


def test_unregistered_skin_raises() -> None:
    with pytest.raises(ValueError, match="Unknown skin: 'nonexistent'"):
        render(50.0, config={"skin": "nonexistent"})


def test_telltale_none_value_omitted() -> None:
    img_with_none = render(50.0, telltales={"m1": None, "m10": 60.0})
    img_without_m1 = render(50.0, telltales={"m10": 60.0})
    assert img_with_none.tobytes() == img_without_m1.tobytes()


def test_telltale_all_none_matches_no_telltales() -> None:
    img_all_none = render(50.0, telltales={"m1": None, "m10": None, "h1": None, "all_time": None})
    img_no_tell = render(50.0, telltales=None)
    assert img_all_none.tobytes() == img_no_tell.tobytes()


def test_render_returns_rgba_image() -> None:
    img = render(0.0)
    assert img.mode == "RGBA"

    img2 = render(100.0)
    assert img2.mode == "RGBA"


def test_render_integer_value_accepted() -> None:
    img = render(75)
    assert isinstance(img, Image.Image)
    assert img.size == (DEFAULT_GAUGE_SIZE, DEFAULT_GAUGE_SIZE)


def test_render_minimum_size() -> None:
    img = render(50.0, size=MIN_GAUGE_SIZE)
    assert img.size == (MIN_GAUGE_SIZE, MIN_GAUGE_SIZE)


def test_render_config_none_uses_stingray() -> None:
    img1 = render(50.0, config=None)
    img2 = render(50.0, config={"skin": "stingray"})
    assert img1.tobytes() == img2.tobytes()


def test_render_full_telltales() -> None:
    img = render(50.0, telltales={"m1": 25.0, "m10": 50.0, "h1": 75.0, "all_time": 90.0})
    assert isinstance(img, Image.Image)
    assert img.size == (DEFAULT_GAUGE_SIZE, DEFAULT_GAUGE_SIZE)


def test_render_boundary_values() -> None:
    img_zero = render(0.0)
    assert isinstance(img_zero, Image.Image)

    img_hundred = render(100.0)
    assert isinstance(img_hundred, Image.Image)

    assert img_zero.tobytes() != img_hundred.tobytes()