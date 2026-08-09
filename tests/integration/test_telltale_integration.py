"""Integration tier tests routing synthetic metric streams through TelltaleManager to TelltaleRenderer.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import pytest
from PIL import Image, ImageChops

from boostgauge.telltale_renderer import TelltaleManager, TelltaleRenderer, GaugeGeometry


def test_telltale_stream_integration_render():
    """Pipe a synthetic metric stream into TelltaleManager and render on PIL surface."""
    mgr = TelltaleManager()
    renderer = TelltaleRenderer()
    base_face = Image.new("RGBA", (256, 256), (20, 20, 20, 255))

    for t in range(0, 100):
        val = 85.0 if t == 30 else 40.0
        mgr.update(float(t), float(val))

    peaks_at_90 = mgr.current_peaks(90.0)
    assert peaks_at_90["1m"] == 85.0
    assert peaks_at_90["10m"] == 85.0

    rendered = renderer.render_telltales(base_face, peaks_at_90, render_legend=True)
    assert rendered is not None
    assert rendered.size == (256, 256)

    peaks_at_100 = mgr.current_peaks(100.0)
    assert peaks_at_100["1m"] == 40.0
    assert peaks_at_100["10m"] == 85.0

    rendered_100 = renderer.render_telltales(base_face, peaks_at_100, render_legend=True)
    assert rendered_100 is not None


def test_telltale_all_time_window_never_expires():
    """Verify all_time peak persists indefinitely regardless of timestamp."""
    mgr = TelltaleManager()

    mgr.update(0.0, 99.0)

    peaks_far_future = mgr.current_peaks(1_000_000.0)
    assert peaks_far_future["all_time"] == 99.0


def test_telltale_1m_window_expires_correctly():
    """Verify 1m window drops peak after 60 seconds have elapsed."""
    mgr = TelltaleManager()

    mgr.update(0.0, 90.0)
    mgr.update(1.0, 10.0)

    peaks_before_expiry = mgr.current_peaks(59.0)
    assert peaks_before_expiry["1m"] == 90.0

    peaks_after_expiry = mgr.current_peaks(62.0)
    assert peaks_after_expiry["1m"] == 10.0


def test_telltale_reset_mid_stream_clears_and_resumes():
    """Verify reset mid-stream clears peak and new samples are tracked correctly."""
    mgr = TelltaleManager()

    for t in range(0, 50):
        mgr.update(float(t), 75.0)

    mgr.reset("1m")
    assert mgr.current_peaks(50.0)["1m"] is None

    mgr.update(50.0, 30.0)
    assert mgr.current_peaks(50.0)["1m"] == 30.0


def test_render_produces_pixel_changes_for_active_peaks():
    """Verify rendering active peaks modifies pixels compared to blank base image."""
    mgr = TelltaleManager()
    renderer = TelltaleRenderer()
    base = Image.new("RGBA", (256, 256), (30, 30, 30, 255))

    mgr.update(0.0, 50.0)
    peaks = mgr.current_peaks(0.0)

    rendered = renderer.render_telltales(base, peaks, render_legend=False)
    diff = ImageChops.difference(base, rendered)
    assert diff.getbbox() is not None


def test_render_no_pixel_changes_when_all_peaks_none():
    """Verify rendering all-None peaks returns an image equal to the base."""
    renderer = TelltaleRenderer()
    base = Image.new("RGBA", (256, 256), (30, 30, 30, 255))
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    rendered = renderer.render_telltales(base, peaks, render_legend=False)
    diff = ImageChops.difference(base, rendered)
    assert diff.getbbox() is None


def test_render_legend_visible_when_peaks_active():
    """Verify legend region differs from base when peaks are active and render_legend=True."""
    mgr = TelltaleManager()
    renderer = TelltaleRenderer()
    base = Image.new("RGBA", (256, 256), (30, 30, 30, 255))

    mgr.update(0.0, 50.0)
    peaks = mgr.current_peaks(0.0)

    rendered_with_legend = renderer.render_telltales(base, peaks, render_legend=True)
    rendered_no_legend = renderer.render_telltales(base, peaks, render_legend=False)

    diff = ImageChops.difference(rendered_with_legend, rendered_no_legend)
    assert diff.getbbox() is not None


def test_render_rgb_base_converted_to_rgba():
    """Verify TelltaleRenderer handles RGB base images by converting to RGBA."""
    mgr = TelltaleManager()
    renderer = TelltaleRenderer()
    base_rgb = Image.new("RGB", (256, 256), (40, 40, 40))

    mgr.update(0.0, 60.0)
    peaks = mgr.current_peaks(0.0)

    rendered = renderer.render_telltales(base_rgb, peaks, render_legend=False)
    assert rendered.mode == "RGBA"
    assert rendered.size == (256, 256)


def test_render_output_size_matches_non_standard_base():
    """Verify rendered output preserves non-standard image dimensions."""
    mgr = TelltaleManager()
    renderer = TelltaleRenderer()
    base = Image.new("RGBA", (512, 512), (20, 20, 20, 255))

    mgr.update(0.0, 70.0)
    peaks = mgr.current_peaks(0.0)

    rendered = renderer.render_telltales(base, peaks, render_legend=True)
    assert rendered.size == (512, 512)


def test_multiple_reset_cycles_track_new_peaks():
    """Verify that repeated reset-and-update cycles track fresh peaks correctly."""
    mgr = TelltaleManager()

    mgr.update(0.0, 95.0)
    assert mgr.current_peaks(0.0)["all_time"] == 95.0

    mgr.reset()
    assert mgr.current_peaks(0.0)["all_time"] is None

    mgr.update(1.0, 50.0)
    assert mgr.current_peaks(1.0)["all_time"] == 50.0

    mgr.reset()
    mgr.update(2.0, 80.0)
    assert mgr.current_peaks(2.0)["all_time"] == 80.0


def test_peak_holds_maximum_over_varied_stream():
    """Verify peak holds the maximum across a varied value stream."""
    mgr = TelltaleManager()

    values = [10.0, 55.0, 30.0, 88.0, 45.0, 22.0]
    for i, v in enumerate(values):
        mgr.update(float(i), v)

    peaks = mgr.current_peaks(float(len(values) - 1))
    assert peaks["all_time"] == 88.0


def test_stream_integration_four_windows_diverge_over_time():
    """Verify shorter windows diverge from longer windows as peaks age out."""
    mgr = TelltaleManager()

    mgr.update(0.0, 100.0)

    for t in range(1, 70):
        mgr.update(float(t), 20.0)

    peaks = mgr.current_peaks(70.0)

    assert peaks["1m"] == 20.0
    assert peaks["10m"] == 100.0
    assert peaks["1h"] == 100.0
    assert peaks["all_time"] == 100.0


def test_render_does_not_mutate_base_image():
    """Verify render_telltales does not modify the original base image."""
    mgr = TelltaleManager()
    renderer = TelltaleRenderer()
    base = Image.new("RGBA", (256, 256), (77, 77, 77, 255))

    mgr.update(0.0, 50.0)
    peaks = mgr.current_peaks(0.0)

    renderer.render_telltales(base, peaks, render_legend=True)

    assert base.getpixel((128, 128)) == (77, 77, 77, 255)


def test_custom_geometry_integration():
    """Verify TelltaleRenderer with custom geometry integrates correctly with TelltaleManager."""
    mgr = TelltaleManager()
    geo = GaugeGeometry(
        center_x=64.0,
        center_y=64.0,
        radius=50.0,
        start_angle_deg=135.0,
        end_angle_deg=405.0,
        min_value=0.0,
        max_value=100.0,
    )
    renderer = TelltaleRenderer(geometry=geo)
    base = Image.new("RGBA", (128, 128), (10, 10, 10, 255))

    mgr.update(0.0, 75.0)
    peaks = mgr.current_peaks(0.0)

    rendered = renderer.render_telltales(base, peaks, render_legend=False)
    assert rendered.size == (128, 128)
    assert rendered.mode == "RGBA"

    diff = ImageChops.difference(base, rendered)
    assert diff.getbbox() is not None