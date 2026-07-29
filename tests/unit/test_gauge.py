"""Unit test suite for core gauge renderer math, validation, and skin protocol compliance.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
Ref: docs/design/0001-test-strategy.md (Option C / off-screen PIL renderer)
"""

from __future__ import annotations

import sys
from PIL import Image
import pytest

from boostgauge.gauge import render, validate_render_inputs
from boostgauge.skins.stingray import calculate_angle, render_stingray
from boostgauge.skins import get_skin_renderer, SKIN_REGISTRY


def test_t010_pure_function_rendering_without_gui() -> None:
    """T010: Verify render() returns a PIL.Image.Image without importing tkinter."""
    img = render(value=50.0, telltales=None, size=256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"
    assert "tkinter" not in sys.modules


def test_t020_input_clamping_and_bounds_validation() -> None:
    """T020: Verify value clamping to [0, 100] and size clamping to minimum 128."""
    v1, s1 = validate_render_inputs(-25.0, 256)
    assert v1 == 0.0
    assert s1 == 256

    v2, s2 = validate_render_inputs(150.0, 256)
    assert v2 == 100.0
    assert s2 == 256

    v3, s3 = validate_render_inputs(50.0, 64)
    assert v3 == 50.0
    assert s3 == 128

    v4, _ = validate_render_inputs(float("nan"), 256)
    assert v4 == 0.0


def test_t020_size_clamped_to_minimum_128() -> None:
    """T020: Verify size=0 and negative size are clamped to 128."""
    _, s1 = validate_render_inputs(50.0, 0)
    assert s1 == 128

    _, s2 = validate_render_inputs(50.0, -10)
    assert s2 == 128


def test_t020_default_canvas_size_256() -> None:
    """T020: Verify render() with default size returns 256x256 image."""
    img = render(value=0.0)
    assert img.size == (256, 256)


def test_t030_angle_mapping_zero() -> None:
    """T030: value=0 maps to 225 degrees."""
    assert calculate_angle(0.0) == pytest.approx(225.0)


def test_t030_angle_mapping_midpoint() -> None:
    """T030: value=50 maps to 90 degrees."""
    assert calculate_angle(50.0) == pytest.approx(90.0)


def test_t030_angle_mapping_max() -> None:
    """T030: value=100 maps to -45 degrees."""
    assert calculate_angle(100.0) == pytest.approx(-45.0)


def test_t030_angle_mapping_quarter() -> None:
    """T030: value=25 maps to 157.5 degrees."""
    assert calculate_angle(25.0) == pytest.approx(157.5)


def test_t030_angle_mapping_three_quarter() -> None:
    """T030: value=75 maps to 22.5 degrees."""
    assert calculate_angle(75.0) == pytest.approx(22.5)


def test_t030_angle_mapping_is_linear() -> None:
    """T030: Angle mapping is linear — midpoint between 0 and 100 is midpoint of angle range."""
    a0 = calculate_angle(0.0)
    a100 = calculate_angle(100.0)
    a50 = calculate_angle(50.0)
    assert a50 == pytest.approx((a0 + a100) / 2.0)


def test_t090_skin_protocol_routing_default() -> None:
    """T090: render() with no config dispatches to stingray skin."""
    img = render(value=30.0, size=128)
    assert isinstance(img, Image.Image)
    assert img.size == (128, 128)


def test_t090_skin_protocol_routing_explicit_stingray() -> None:
    """T090: render() with config skin=stingray dispatches correctly."""
    img = render(value=30.0, size=128, config={"skin": "stingray"})
    assert isinstance(img, Image.Image)
    assert img.size == (128, 128)


def test_t090_skin_protocol_routing_unknown_falls_back() -> None:
    """T090: Unknown skin name falls back to stingray."""
    img = render(value=30.0, size=128, config={"skin": "nonexistent_skin"})
    assert isinstance(img, Image.Image)
    assert img.size == (128, 128)


def test_t090_skin_registry_contains_stingray() -> None:
    """T090: SKIN_REGISTRY exposes stingray entry."""
    assert "stingray" in SKIN_REGISTRY
    assert callable(SKIN_REGISTRY["stingray"])


def test_t090_get_skin_renderer_returns_callable() -> None:
    """T090: get_skin_renderer() returns a callable for known and unknown skins."""
    renderer = get_skin_renderer("stingray")
    assert callable(renderer)

    fallback = get_skin_renderer("unknown")
    assert callable(fallback)


def test_render_stingray_returns_rgba_image() -> None:
    """T080: render_stingray() returns RGBA PIL.Image at requested size."""
    img = render_stingray(value=0.0, size=256)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"
    assert img.size == (256, 256)


def test_render_stingray_telltales_none_unchanged() -> None:
    """T080: render_stingray() with telltales=None returns valid image."""
    img = render_stingray(value=50.0, telltales=None, size=128)
    assert isinstance(img, Image.Image)
    assert img.size == (128, 128)


def test_render_stingray_with_telltales() -> None:
    """T080: render_stingray() with active telltales returns valid image."""
    telltales = {"m1": 55.0, "m10": 70.0, "h1": 85.0, "all": 95.0}
    img = render_stingray(value=40.0, telltales=telltales, size=128)
    assert isinstance(img, Image.Image)
    assert img.size == (128, 128)


def test_render_no_tkinter_side_effects() -> None:
    """T010: Repeated render calls do not import tkinter."""
    for v in [0.0, 25.0, 50.0, 75.0, 100.0]:
        render(value=v, size=128)
    assert "tkinter" not in sys.modules


def test_validate_render_inputs_boundary_values() -> None:
    """T020: Exact boundary values 0.0 and 100.0 are preserved unchanged."""
    v1, _ = validate_render_inputs(0.0, 256)
    assert v1 == 0.0

    v2, _ = validate_render_inputs(100.0, 256)
    assert v2 == 100.0


def test_validate_render_inputs_size_max_clamped() -> None:
    """T020: Size values above 1024 are clamped to 1024."""
    _, s = validate_render_inputs(50.0, 9999)
    assert s == 1024


def test_render_output_is_not_mutated_across_calls() -> None:
    """T010: Two calls with same inputs return independently usable images."""
    img1 = render(value=50.0, size=128)
    img2 = render(value=50.0, size=128)
    assert img1 is not img2