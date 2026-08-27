"""Test file for Issue #331.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

from PIL import Image
from boostgauge.skins.stingray import render_face, _polar


def test_010_basic_render_signature():
    # Basic render signature and object (REQ-1) -- expected: Object is PIL.Image, dimensions (256, 256), no needle rendering invoked
    img = render_face(256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)


def test_020_dial_face_flat_fill():
    # Dial face flat fill (REQ-2) -- expected: Classification at 3 interior points + equality of samples at (0.3 R, 0.5 R, 0.7 R) to flat #0A0A0C
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    # Baseline-independent logic checks specific radial pixels at 45 degrees
    for radius_frac in [0.3, 0.5, 0.7]:
        x, y = _polar(cx, cy, R * radius_frac, 45.0)
        assert rgb_img.getpixel((int(x), int(y))) == (10, 10, 12)


def test_030_redline_band_rendering():
    # Redline band rendering (REQ-2) -- expected: Classification at radius 0.94 R at values 65/75/85 equals #AA0F19
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    from boostgauge.skins.stingray import _val_to_deg
    for val in (65, 75, 85):
        deg = _val_to_deg(val)
        x, y = _polar(cx, cy, R * 0.94, deg)
        assert rgb_img.getpixel((int(x), int(y))) == (170, 15, 25)


def test_040_major_ticks_rendering():
    # Major ticks rendering (REQ-2) -- expected: Stroke predicate at each tick's midpoint: channel mean >= 100, all 11
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    from boostgauge.skins.stingray import _val_to_deg
    for val in range(0, 101, 10):
        deg = _val_to_deg(val)
        x, y = _polar(cx, cy, R * 0.91, deg)
        r, g, b = rgb_img.getpixel((int(x), int(y)))
        assert (r + g + b) / 3.0 >= 100


def test_050_minor_ticks_rendering():
    # Minor ticks rendering (REQ-2) -- expected: Stroke predicate at 4 sampled minors (values 2, 34, 66, 98): midpoint channel mean >= 100
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    from boostgauge.skins.stingray import _val_to_deg
    for val in (2, 34, 66, 98):
        deg = _val_to_deg(val)
        x, y = _polar(cx, cy, R * 0.93, deg)
        r, g, b = rgb_img.getpixel((round(x), round(y)))
        assert (r + g + b) / 3.0 >= 100


def test_060_numerals_presence():
    # Numerals presence (REQ-2) -- expected: >=1 white-classified pixel within the numeral's cap-height box at each of the 11 positions at 0.72 R
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    from boostgauge.skins.stingray import _val_to_deg
    for val in range(0, 101, 10):
        deg = _val_to_deg(val)
        nx, ny = _polar(cx, cy, R * 0.72, deg)
        box = (int(nx - 5), int(ny - 5), int(nx + 5), int(ny + 5))
        white_pixels = sum(1 for x in range(box[0], box[2]) for y in range(box[1], box[3]) if rgb_img.getpixel((x, y)) == (255, 255, 255))
        assert white_pixels >= 1


def test_070_wordmark_presence():
    # Wordmark presence (REQ-2) -- expected: >=1 white-classified pixel in the wordmark band; absence of white in the mirror band above the pivot, sampled ONLY at horizontal offsets 0.12 R-0.25 R either side of the vertical axis
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    # Wordmark band below pivot
    wy = cy + R * 0.67
    white_pixels = 0
    for dx in range(int(R * 0.12), int(R * 0.25) + 1):
        for side in (-1, 1):
            if rgb_img.getpixel((int(cx + side * dx), int(wy))) == (255, 255, 255):
                white_pixels += 1
    assert white_pixels >= 1
    
    # Mirror band above pivot
    my = cy - R * 0.67
    mirror_white = 0
    for dx in range(int(R * 0.12), int(R * 0.25) + 1):
        for side in (-1, 1):
            if rgb_img.getpixel((int(cx + side * dx), int(my))) == (255, 255, 255):
                mirror_white += 1
    assert mirror_white == 0


def test_080_chrome_housing_rendering():
    # Chrome housing rendering (REQ-2) -- expected: >=3 achromatic samples spanning the horizon, >=1 dark (mean < 100), >=1 bright (mean > 200)
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    
    achromatic_means = []
    # Sample spanning the horizon (y-axis center)
    for x in range(img.width):
        r, g, b = rgb_img.getpixel((x, int(cy)))
        if max(r, g, b) - min(r, g, b) <= 14:
            mean = (r + g + b) / 3.0
            if 16 <= mean <= 248:
                achromatic_means.append(mean)
                
    assert len(achromatic_means) >= 3
    assert any(m < 100 for m in achromatic_means)
    assert any(m > 200 for m in achromatic_means)


def test_090_screws_rendering():
    # Screws rendering (REQ-2) -- expected: Centre pixel within +-6 per channel of #1A1A1C at pivot + (-0.25 R, 0) and (+0.25 R, 0)
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    for dx in (-0.25 * R, 0.25 * R):
        sx, sy = cx + dx, cy
        r, g, b = rgb_img.getpixel((int(sx), int(sy)))
        assert abs(r - 26) <= 6
        assert abs(g - 26) <= 6
        assert abs(b - 28) <= 6


def test_100_bezel_seat_rendering():
    # Bezel seat rendering (REQ-2) -- expected: Sample at 1.01 R is darker (channel mean) than the chrome at 1.10 R on the same radial
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    shadow = rgb_img.getpixel((int(cx), int(cy + R * 1.01)))
    chrome = rgb_img.getpixel((int(cx), int(cy + R * 1.10)))
    assert (sum(shadow) / 3.0) < (sum(chrome) / 3.0)


def test_110_caching_behavior():
    # Image caching verification (REQ-3) -- expected: Identical object memory reference
    img1 = render_face(256)
    img2 = render_face(256)
    assert img1 is img2


def test_120_constant_encapsulation(tmp_path):
    # Constant encapsulation check (REQ-4) -- expected: AST/Regex verification ensuring values like #AA0F19 do not appear outside src/boostgauge/skins/
    import re
    from pathlib import Path
    
    src_dir = Path(__file__).parent.parent.parent / "src" / "boostgauge"
    dial_color_pattern = re.compile(r'\(\s*(?:170\s*,\s*15\s*,\s*25|10\s*,\s*10\s*,\s*12|26\s*,\s*26\s*,\s*28)\s*\)')
    
    assert src_dir.exists(), "Source directory not found"
    for py_file in src_dir.rglob("*.py"):
        if "skins" in py_file.parts:
            continue
        content = py_file.read_text(encoding="utf-8")
        assert not dial_color_pattern.search(content), f"Dial color constant found in {py_file}"


def test_130_artifact_emission(tmp_path, capsys):
    # Artifact emission on CLI flag (REQ-5) -- expected: File exists in run's artifacts directory and stdout contains its absolute path
    import sys
    from pathlib import Path
    
    sys.path.insert(0, str(Path(__file__).parent))
    import conftest
    sys.path.pop(0)
    
    class MockConfig:
        def getoption(self, name, default=False):
            return True
            
    conftest.generate_baselines_if_requested(MockConfig(), Path(tmp_path))
    
    out_path = Path(tmp_path) / "face-256.png"
    captured = capsys.readouterr()
    assert out_path.exists()
    
    # MUST strictly use Path-based comparisons for platform independence
    stdout_path = Path(captured.out.strip())
    assert stdout_path.resolve() == out_path.resolve()
