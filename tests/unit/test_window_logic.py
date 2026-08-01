"""Headless unit tests for window geometry logic state machine.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import pytest
from boostgauge.config import WindowConfigDict
from boostgauge.window import WindowStateController


@pytest.fixture
def baseline_config() -> WindowConfigDict:
    return {
        "x": 200,
        "y": 300,
        "size": 256,
        "topmost": True,
        "opacity": 1.0,
        "compact_mode": False,
    }


def test_t010_initial_controller_state(baseline_config: WindowConfigDict):
    """T010: Controller initializes with exact config values."""
    controller = WindowStateController(baseline_config)
    assert controller.x == 200
    assert controller.y == 300
    assert controller.size == 256
    assert controller.topmost is True
    assert controller.opacity == 1.0
    assert controller.compact_mode is False


def test_t010_initial_controller_min_max_defaults(baseline_config: WindowConfigDict):
    """T010: Controller uses default min/max size bounds."""
    controller = WindowStateController(baseline_config)
    assert controller.min_size == 128
    assert controller.max_size == 512


def test_t010_initial_controller_custom_bounds(baseline_config: WindowConfigDict):
    """T010: Controller respects custom min/max size bounds."""
    controller = WindowStateController(baseline_config, min_size=64, max_size=1024)
    assert controller.min_size == 64
    assert controller.max_size == 1024


def test_t030_compute_drag_move(baseline_config: WindowConfigDict):
    """T030: Drag delta calculation returns updated position."""
    controller = WindowStateController(baseline_config)
    new_pos = controller.compute_drag_move(200, 300, 50, -20)
    assert new_pos == (250, 280)
    assert controller.x == 250
    assert controller.y == 280


def test_t030_compute_drag_move_zero_delta(baseline_config: WindowConfigDict):
    """T030: Zero drag delta returns unchanged origin."""
    controller = WindowStateController(baseline_config)
    new_pos = controller.compute_drag_move(200, 300, 0, 0)
    assert new_pos == (200, 300)
    assert controller.x == 200
    assert controller.y == 300


def test_t030_compute_drag_move_negative_result(baseline_config: WindowConfigDict):
    """T030: Negative delta can produce negative coordinates (bounds checked separately)."""
    controller = WindowStateController(baseline_config)
    new_pos = controller.compute_drag_move(10, 10, -50, -50)
    assert new_pos == (-40, -40)
    assert controller.x == -40
    assert controller.y == -40


def test_t030_compute_drag_move_large_delta(baseline_config: WindowConfigDict):
    """T030: Large positive delta moves window far."""
    controller = WindowStateController(baseline_config)
    new_pos = controller.compute_drag_move(100, 100, 800, 600)
    assert new_pos == (900, 700)


def test_t040_geometry_string_formatting(baseline_config: WindowConfigDict):
    """T040: Format geometry string matches Tkinter 'WxH+X+Y' syntax."""
    controller = WindowStateController(baseline_config)
    assert controller.get_geometry_string() == "256x256+200+300"


def test_t040_geometry_string_after_drag(baseline_config: WindowConfigDict):
    """T040: Geometry string updates after drag move."""
    controller = WindowStateController(baseline_config)
    controller.compute_drag_move(200, 300, 100, 50)
    assert controller.get_geometry_string() == "256x256+300+350"


def test_t040_geometry_string_square_aspect_ratio(baseline_config: WindowConfigDict):
    """T040: Width and height in geometry string are always equal (1:1 ratio)."""
    controller = WindowStateController(baseline_config)
    geom = controller.get_geometry_string()
    parts = geom.split("+")[0].split("x")
    assert parts[0] == parts[1]


def test_t040_geometry_string_at_origin():
    """T040: Geometry string at origin position."""
    config: WindowConfigDict = {
        "x": 0,
        "y": 0,
        "size": 128,
        "topmost": True,
        "opacity": 1.0,
        "compact_mode": False,
    }
    controller = WindowStateController(config)
    assert controller.get_geometry_string() == "128x128+0+0"


def test_t050_toggle_compact_mode(baseline_config: WindowConfigDict):
    """T050: Double-click compact mode toggles between 128px and 256px."""
    controller = WindowStateController(baseline_config)
    size1, compact1 = controller.toggle_compact_mode()
    assert size1 == 128
    assert compact1 is True
    assert controller.size == 128
    assert controller.compact_mode is True

    size2, compact2 = controller.toggle_compact_mode()
    assert size2 == 256
    assert compact2 is False
    assert controller.size == 256
    assert controller.compact_mode is False


def test_t050_toggle_compact_mode_repeated(baseline_config: WindowConfigDict):
    """T050: Repeated toggles alternate correctly."""
    controller = WindowStateController(baseline_config)
    for i in range(4):
        size, compact = controller.toggle_compact_mode()
        if i % 2 == 0:
            assert size == 128
            assert compact is True
        else:
            assert size == 256
            assert compact is False


def test_t050_toggle_compact_mode_from_compact():
    """T050: Toggle from compact state returns expanded mode."""
    config: WindowConfigDict = {
        "x": 100,
        "y": 100,
        "size": 128,
        "topmost": True,
        "opacity": 1.0,
        "compact_mode": True,
    }
    controller = WindowStateController(config)
    size, compact = controller.toggle_compact_mode()
    assert size == 256
    assert compact is False


def test_t130_compute_wheel_resize_scroll_up(baseline_config: WindowConfigDict):
    """T130: Scroll up increases size by step."""
    controller = WindowStateController(baseline_config, min_size=128, max_size=512)
    new_size = controller.compute_wheel_resize(256, 1, step_size=32)
    assert new_size == 288
    assert controller.size == 288


def test_t130_compute_wheel_resize_scroll_down(baseline_config: WindowConfigDict):
    """T130: Scroll down decreases size by step."""
    controller = WindowStateController(baseline_config, min_size=128, max_size=512)
    new_size = controller.compute_wheel_resize(256, -1, step_size=32)
    assert new_size == 224
    assert controller.size == 224


def test_t130_compute_wheel_resize_max_clamp(baseline_config: WindowConfigDict):
    """T130: Resizing beyond max_size returns max_size."""
    controller = WindowStateController(baseline_config, min_size=128, max_size=512)
    new_size = controller.compute_wheel_resize(500, 1, step_size=50)
    assert new_size == 512


def test_t130_compute_wheel_resize_min_clamp(baseline_config: WindowConfigDict):
    """T130: Resizing below min_size returns min_size."""
    controller = WindowStateController(baseline_config, min_size=128, max_size=512)
    new_size = controller.compute_wheel_resize(140, -1, step_size=50)
    assert new_size == 128


def test_t130_compute_wheel_resize_at_max_boundary(baseline_config: WindowConfigDict):
    """T130: Scrolling up at exact max returns max unchanged."""
    controller = WindowStateController(baseline_config, min_size=128, max_size=512)
    new_size = controller.compute_wheel_resize(512, 1, step_size=32)
    assert new_size == 512


def test_t130_compute_wheel_resize_at_min_boundary(baseline_config: WindowConfigDict):
    """T130: Scrolling down at exact min returns min unchanged."""
    controller = WindowStateController(baseline_config, min_size=128, max_size=512)
    new_size = controller.compute_wheel_resize(128, -1, step_size=32)
    assert new_size == 128


def test_t130_compute_wheel_resize_custom_step(baseline_config: WindowConfigDict):
    """T130: Custom step_size applies correctly."""
    controller = WindowStateController(baseline_config, min_size=128, max_size=512)
    new_size = controller.compute_wheel_resize(256, 1, step_size=64)
    assert new_size == 320


def test_t140_aspect_ratio_preserved_after_resize(baseline_config: WindowConfigDict):
    """T140: After wheel resize, geometry string has equal width and height."""
    controller = WindowStateController(baseline_config)
    controller.compute_wheel_resize(256, 1, step_size=32)
    geom = controller.get_geometry_string()
    parts = geom.split("+")[0].split("x")
    assert parts[0] == parts[1]
    assert parts[0] == "288"


def test_t140_aspect_ratio_preserved_after_compact_toggle(baseline_config: WindowConfigDict):
    """T140: After compact toggle, geometry string has equal width and height."""
    controller = WindowStateController(baseline_config)
    controller.toggle_compact_mode()
    geom = controller.get_geometry_string()
    parts = geom.split("+")[0].split("x")
    assert parts[0] == parts[1]
    assert parts[0] == "128"


def test_t150_dpi_scaling_factor_math(baseline_config: WindowConfigDict):
    """T150: DPI scaling geometry adjustment."""
    controller = WindowStateController(baseline_config)
    scaled_150 = controller.calculate_dpi_scaled_size(256, 1.5)
    assert scaled_150 == 384

    scaled_100 = controller.calculate_dpi_scaled_size(256, 1.0)
    assert scaled_100 == 256


def test_t150_dpi_scaling_rounds_correctly(baseline_config: WindowConfigDict):
    """T150: DPI scale produces rounded integer result."""
    controller = WindowStateController(baseline_config)
    result = controller.calculate_dpi_scaled_size(100, 1.5)
    assert isinstance(result, int)
    assert result == 150


def test_t150_dpi_scaling_zero_raises(baseline_config: WindowConfigDict):
    """T150: dpi_scale <= 0 raises ValueError."""
    controller = WindowStateController(baseline_config)
    with pytest.raises(ValueError, match="dpi_scale must be positive"):
        controller.calculate_dpi_scaled_size(256, 0.0)


def test_t150_dpi_scaling_negative_raises(baseline_config: WindowConfigDict):
    """T150: Negative dpi_scale raises ValueError."""
    controller = WindowStateController(baseline_config)
    with pytest.raises(ValueError, match="dpi_scale must be positive"):
        controller.calculate_dpi_scaled_size(256, -1.5)


def test_t150_dpi_scaling_fractional(baseline_config: WindowConfigDict):
    """T150: Fractional DPI scale rounds to nearest integer."""
    controller = WindowStateController(baseline_config)
    result = controller.calculate_dpi_scaled_size(100, 1.25)
    assert result == 125


def test_to_config_dict_roundtrip(baseline_config: WindowConfigDict):
    """to_config_dict returns all current state fields correctly."""
    controller = WindowStateController(baseline_config)
    result = controller.to_config_dict()
    assert result["x"] == 200
    assert result["y"] == 300
    assert result["size"] == 256
    assert result["topmost"] is True
    assert result["opacity"] == 1.0
    assert result["compact_mode"] is False


def test_to_config_dict_reflects_mutations(baseline_config: WindowConfigDict):
    """to_config_dict reflects state after mutations."""
    controller = WindowStateController(baseline_config)
    controller.compute_drag_move(200, 300, 50, 25)
    controller.compute_wheel_resize(256, 1, step_size=32)
    result = controller.to_config_dict()
    assert result["x"] == 250
    assert result["y"] == 325
    assert result["size"] == 288


def test_compute_drag_move_updates_controller_state(baseline_config: WindowConfigDict):
    """compute_drag_move side-effect updates controller x/y."""
    controller = WindowStateController(baseline_config)
    controller.compute_drag_move(200, 300, 10, 20)
    assert controller.x == 210
    assert controller.y == 320
    second_result = controller.compute_drag_move(210, 320, -5, -10)
    assert second_result == (205, 310)
    assert controller.x == 205
    assert controller.y == 310