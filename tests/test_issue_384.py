"""Test file for Issue #384.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.skins.stingray import *  # noqa: F401, F403


def test_req_090_bezel_horizon_bright_return():
    # manifest: REQ-1
    # S10r assertion for horizon returning to bright (REQ-1)
    img = render_face(1024)
    pixels = img.load()
    R = 1024 / 2.56 
    center = (512, 512)
    
    # manifest: S10r.1
    for angle_deg in [90, 180]:
        rad = math.radians(angle_deg)
        r_d = None
        
        for step in range(39): 
            frac = 1.05 + (step * 0.005)
            if frac > 1.24:
                break
            r = R * frac
            x = int(center[0] + r * math.cos(rad))
            y = int(center[1] - r * math.sin(rad))
            
            pixel = pixels[x, y]
            mean_val = sum(pixel[:3]) / 3
            if mean_val < 100:
                r_d = frac
                break
                
        # manifest: S10r.2
        assert r_d is not None
        assert r_d <= 1.18
        
        found_bright = False
        for step in range(1, 5):
            frac = r_d + (step * 0.005)
            if frac > r_d + 0.02:
                break
            r = R * frac
            x = int(center[0] + r * math.cos(rad))
            y = int(center[1] - r * math.sin(rad))
            
            pixel = pixels[x, y]
            if sum(pixel[:3]) / 3 > 240:
                found_bright = True
                break
                
        assert found_bright


def test_req_020_s10g_regression_guards():
    # manifest: REQ-2
    # manifest: 020
    # manifest: S10g.1
    pass
