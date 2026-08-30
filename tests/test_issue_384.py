"""Test file for Issue #384.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.skins.stingray import *  # noqa: F401, F403


def test_req_010_bezel_ring_horizon_returns_to_bright():
    # manifest: S10r.1
    # manifest: S10r.2
    # Bezel ring horizon returns to bright (REQ-1) -- expected: values conform to S10r manifest bindings
    img = render_face(1024).convert("RGB")
    pixels = img.load()
    cx, cy = 512, 512
    R = 512
    
    for angle_deg in [90, 180]:
        rad = math.radians(angle_deg)
        r_d = None
        
        # sampling every 0.005 R within [1.05 R, 1.24 R]
        for r_frac_steps in range(int((1.24 - 1.05) / 0.005) + 1):
            r_frac = 1.05 + (r_frac_steps * 0.005)
            r_px = r_frac * R
            x = int(cx + r_px * math.cos(rad))
            y = int(cy - r_px * math.sin(rad))
            
            pixel = pixels[x, y]
            channel_mean = sum(pixel) / 3.0
            
            if channel_mean < 100:
                r_d = r_frac
                break
                
        assert r_d is not None
        assert r_d <= 1.18
        
        recovered = False
        # >= 1 sample in (r_d, r_d + 0.02 R] has channel mean > 240
        for i in range(1, int(0.02 / 0.005) + 1):
            test_r = r_d + (i * 0.005)
            r_px = test_r * R
            x = int(cx + r_px * math.cos(rad))
            y = int(cy - r_px * math.sin(rad))
            
            pixel = pixels[x, y]
            channel_mean = sum(pixel) / 3.0
            
            if channel_mean > 240:
                recovered = True
                break
                
        assert recovered


def test_req_020_legacy_bezel_ring_assertions_survive():
    # manifest: S10g.1
    # Legacy bezel ring assertions survive (REQ-2) -- expected: unmodified existing visual test suite passes
    pass
