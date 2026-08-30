"""Test file for Issue #379.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.skins.stingray import *  # noqa: F401, F403


def test_req_010_verify_flat_housing_channel_mean():
    # manifest: S7.1
    # manifest: S7.2
    # manifest: S7.3
    # manifest: S7.4
    # Flat housing channel mean & max-min constraints (REQ-1) -- expected: Channel mean 16–248 and max−min ≤ 45 across flat housing regions
    img = render_face(256)
    pixels = img.load()
    size = 256
    corners = [(int(0.12*size), int(0.08*size)), (int(0.88*size), int(0.08*size)), 
               (int(0.12*size), int(0.92*size)), (int(0.88*size), int(0.92*size))]
    for cx, cy in corners:
        px = pixels[cx, cy]
        mean = sum(px[:3]) / 3
        assert 16 <= mean <= 248
        assert max(px[:3]) - min(px[:3]) <= 45


def test_req_020_verify_flat_housing_corners():
    # manifest: S7.5
    # manifest: S7.7
    # Flat housing corner stop values (REQ-1) -- expected: Pixel at (0.12, 0.08) × size within ±10 per channel of (232, 240, 251), and pixel at (0.12, 0.92) × size within ±10 per channel of (219, 214, 204)
    img = render_face(256)
    pixels = img.load()
    size = 256
    sky_y = int(0.08 * size)
    ground_y = int(0.92 * size)
    x = int(0.12 * size)
    sky_px = pixels[x, sky_y]
    ground_px = pixels[x, ground_y]
    for c, val in enumerate((232, 240, 251)):
        assert abs(sky_px[c] - val) <= 10
    for c, val in enumerate((219, 214, 204)):
        assert abs(ground_px[c] - val) <= 10


def test_req_030_verify_flat_housing_verticality():
    # manifest: S7.6
    # manifest: S7.8
    # Flat housing vertical symmetry (REQ-1) -- expected: abs(channel-mean at (0.12, y) − channel-mean at (0.88, y)) ≤ 12 for y ∈ {0.08, 0.92} × size
    img = render_face(256)
    pixels = img.load()
    size = 256
    x = int(0.12 * size)
    opp_x = int(0.88 * size)
    for y_frac in (0.08, 0.92):
        y = int(y_frac * size)
        px_left = pixels[x, y]
        px_right = pixels[opp_x, y]
        mean_left = sum(px_left[:3]) / 3
        mean_right = sum(px_right[:3]) / 3
        assert abs(mean_left - mean_right) <= 12


def test_req_040_verify_bezel_ring_span():
    # manifest: S10.1
    # Bezel ring compressed horizon span (REQ-2) -- expected: At math angles 45, 90, 135, 180, 225, 315 within 1.035-1.24 R: >=1 sample < 100 AND >=1 sample > 200
    img = render_face(256)
    pixels = img.load()
    size = 256
    R = 0.40 * size
    cx = cy = size / 2
    for angle_deg in [45, 90, 135, 180, 225, 315]:
        rad = math.radians(angle_deg)
        has_dark = False
        has_bright = False
        for r_step in range(math.ceil(1.035 * R), int(1.24 * R), 2):
            px_x = int(cx + r_step * math.cos(rad))
            px_y = int(cy + r_step * math.sin(rad))
            mean = sum(pixels[px_x, px_y][:3]) / 3
            if mean < 100: has_dark = True
            if mean > 200: has_bright = True
        assert has_dark and has_bright, f"Failed dark/bright span at {angle_deg}"


def test_req_050_verify_bezel_ring_step():
    # manifest: S10.2
    # Bezel ring adjacent sample step (REQ-2) -- expected: At 90 and 180 radials: max step between adjacent 2px samples >= 150
    img = render_face(256)
    pixels = img.load()
    size = 256
    R = 0.40 * size
    cx = cy = size / 2
    for angle_deg in [90, 180]:
        rad = math.radians(angle_deg)
        max_step = 0
        prev_mean = None
        for r_step in range(math.ceil(1.035 * R), int(1.24 * R), 2):
            px_x = int(cx + r_step * math.cos(rad))
            px_y = int(cy + r_step * math.sin(rad))
            mean = sum(pixels[px_x, px_y][:3]) / 3
            if prev_mean is not None:
                step = abs(mean - prev_mean)
                if step > max_step:
                    max_step = step
            prev_mean = mean
        assert max_step >= 150, f"Failed step assertion at {angle_deg}"


def test_req_060_verify_anti_aliased_edge():
    # manifest: S12.1
    # Anti-aliased tick transect (REQ-3) -- expected: 11-px transect at 0.95 R has >=1 sample in [30, 225]
    from boostgauge.skins.stingray import value_to_angle
    img = render_face(256)
    pixels = img.load()
    size = 256
    R = 0.40 * size
    cx = cy = size / 2
    
    angle_deg = value_to_angle(30)
    angle_rad = math.radians(angle_deg)
    perp_rad = angle_rad + math.pi / 2
    
    stroke_edge_offset = 3  # Offset by half the tick width
    center_x = cx + 0.95 * R * math.cos(angle_rad) + stroke_edge_offset * math.cos(perp_rad)
    center_y = cy + 0.95 * R * math.sin(angle_rad) + stroke_edge_offset * math.sin(perp_rad)
    
    has_intermediate = False
    for d in range(-5, 6):
        px_x = int(center_x + d * math.cos(perp_rad))
        px_y = int(center_y + d * math.sin(perp_rad))
        px = pixels[px_x, px_y]
        mean = sum(px[:3]) / 3
        if 30 <= mean <= 225:
            has_intermediate = True
            break
    assert has_intermediate


def test_req_070_dynamic_exclusion():
    # manifest: REQ-4
    # Dynamic component exclusion (REQ-4) -- expected: Returned image bounds exclude dynamic components
    img = render_face(256)
    pixels = img.load()
    center_px = pixels[int(256/2), int(256/2)]
    mean = sum(center_px[:3]) / 3
    assert abs(mean - 10.7) <= 2.0


def test_req_080_value_error():
    # manifest: 010
    import pytest
    with pytest.raises(ValueError):
        render_face(127)
