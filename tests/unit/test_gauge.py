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
    img_with_none = render(50.0, telltales={"m10": None})
    img_no_telltales = render(50.0, telltales=None)
    assert img_with_none.tobytes() == img_no_telltales.tobytes()


def test_telltale_partial_keys() -> None:
    img = render(50.0, telltales={"m1": 25.0, "all_time": 87.5})
    assert isinstance(img, Image.Image)
    assert img.size == (DEFAULT_GAUGE_SIZE, DEFAULT_GAUGE_SIZE)


def test_config_none_defaults_to_stingray() -> None:
    img = render(50.0, config=None)
    assert isinstance(img, Image.Image)
    assert img.size == (DEFAULT_GAUGE_SIZE, DEFAULT_GAUGE_SIZE)


def test_config_missing_skin_key_defaults_to_stingray() -> None:
    img = render(50.0, config={"color_scheme": "default"})
    assert isinstance(img, Image.Image)
    assert img.size == (DEFAULT_GAUGE_SIZE, DEFAULT_GAUGE_SIZE)


def test_value_boundary_zero() -> None:
    img = render(0.0)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"


def test_value_boundary_hundred() -> None:
    img = render(100.0)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"


def test_integer_value_accepted() -> None:
    img = render(50)
    assert isinstance(img, Image.Image)


def test_size_exactly_minimum() -> None:
    img = render(50.0, size=MIN_GAUGE_SIZE)
    assert img.size == (MIN_GAUGE_SIZE, MIN_GAUGE_SIZE)


def test_size_below_minimum_raises() -> None:
    with pytest.raises(ValueError):
        render(50.0, size=127)


def test_all_telltales_provided() -> None:
    img = render(50.0, telltales={"m1": 25.0, "m10": 50.0, "h1": 75.0, "all_time": 95.0})
    assert isinstance(img, Image.Image)
    assert img.size == (DEFAULT_GAUGE_SIZE, DEFAULT_GAUGE_SIZE)