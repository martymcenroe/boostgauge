"""Unit tests for core gauge renderer math, clamping, and skin protocol compliance.

Issue #1: Core Gauge Renderer
"""

from __future__ import annotations

import sys
import pytest
from PIL import Image

from boostgauge.gauge import render, validate_render_inputs
from boostgauge.skins.stingray import calculate_angle, TelltaleDict


def test_t010_pure_function_rendering_no_tkinter():
    """Verify render() returns a PIL Image without importing tkinter."""
    img = render(value=50.0, size=256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"
    assert "tkinter" not in sys.modules


def test_t020_input_clamping_and_bounds():
    """Verify scalar values are clamped to [0, 100] and size to minimum 128."""
    v1, s1 = validate_render_inputs(-20.0, 64)
    assert v1 == 0.0
    assert s1 == 128

    v2, s2 = validate_render_inputs(150.0, 512)
    assert v2 == 100.0
    assert s2 == 512


def test_t030_angle_mapping_calculation():
    """Verify linear mapping of scalar values to needle sweep angles in degrees."""
    assert calculate_angle(0.0) == pytest.approx(225.0)
    assert calculate_angle(50.0) == pytest.approx(90.0)
    assert calculate_angle(100.0) == pytest.approx(-45.0)


def test_t090_skin_protocol_routing():
    """Verify gauge.render routing works with valid skin config and raises on invalid skin."""
    img = render(value=10.0, config={"skin": "stingray"})
    assert isinstance(img, Image.Image)

    with pytest.raises(ValueError, match="Unknown skin"):
        render(value=10.0, config={"skin": "nonexistent_skin"})