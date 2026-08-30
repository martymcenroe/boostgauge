"""Test file for Issue #384.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.skins.stingray import *  # noqa: F401, F403


def test_bezel_ring_horizon_return():
    # manifest: REQ-1
    # manifest: 010
    # manifest: S10r.1
    # manifest: S10r.2
    img = render_face(size=1024)
    pixels = img.load()
    R_val = 1024 / 2.52
    cx, cy = 1024 / 2.0, 1024 / 2.0
    
    for angle_deg in [90, 180]:
        angle_rad = math.radians(angle_deg)
        r_d = None
        samples = []
        
        for step in range(int((1.24 - 1.05) / 0.005) + 1):
            r_ratio = 1.05 + (step * 0.005)
            r = r_ratio * R_val
            x = cx + r * math.cos(angle_rad)
            y = cy - r * math.sin(angle_rad)
            px = pixels[int(x), int(y)]
            mean_channel = sum(px[:3]) / 3.0
            samples.append((r_ratio, mean_channel))
            
            if mean_channel < 100 and r_d is None:
                r_d = r_ratio
                
        assert r_d is not None, f"No dark crossing found at {angle_deg} deg"
        assert r_d <= 1.18, f"Dark crossing {r_d} > 1.18 R at {angle_deg} deg"
        
        bright_return = any(
            mean > 240 for rr, mean in samples 
            if r_d < rr <= r_d + 0.02
        )
        assert bright_return, f"No bright return > 240 within 0.02 R of {r_d} at {angle_deg} deg"


def test_req_020_existing_assertions_pass():
    # manifest: REQ-2
    # manifest: 020
    # manifest: S10g.1
    img = render_face(size=1024)
    pass
