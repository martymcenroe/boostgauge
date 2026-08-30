"""Test file for Issue #384.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.skins.stingray import *  # noqa: F401, F403


def test_req_010_verify_horizon_returns_to_bright():
    # manifest: 010
    # manifest: REQ-1
    # manifest: S10r.1
    # manifest: S10r.2
    # Verify horizon returns to bright (REQ-1) -- Expected: r_d <= 1.18 R, >240 in bracket
    img = render_face(1024)
    pixels = img.load()
    R = 406
    cx, cy = 512, 512
    
    for angle_deg in [90, 180]:
        rad = math.radians(angle_deg)
        r_d = None
        
        # S10r.1: sampling every 0.005 R within [1.05 R, 1.24 R]
        # let r_d be the smallest sampled radius with channel mean < 100
        for r_step in range(round(1.05 / 0.005), round(1.24 / 0.005) + 1):
            r_frac = r_step * 0.005
            r = r_frac * R
            x = int(cx + r * math.cos(rad))
            y = int(cy - r * math.sin(rad)) # math convention, y is inverted in PIL
            val = sum(pixels[x, y][:3]) / 3
            if val < 100:
                r_d = r_frac
                break
                
        # S10r.2: assert r_d exists, r_d <= 1.18 R, and >=1 sample in (r_d, r_d + 0.02 R] has channel mean > 240
        assert r_d is not None, f"No r_d found at angle {angle_deg}"
        assert r_d <= 1.18, f"r_d {r_d} > 1.18 R at angle {angle_deg}"
        
        found_bright = False
        for step in range(1, 5): # 0.005 * 4 = 0.020 R
            r_frac = r_d + step * 0.005
            r = r_frac * R
            x = int(cx + r * math.cos(rad))
            y = int(cy - r * math.sin(rad))
            if sum(pixels[x, y][:3]) / 3 > 240:
                found_bright = True
                break
        assert found_bright, f"No bright bracket found past r_d {r_d} at angle {angle_deg}"


def test_req_020_verify_legacy_bindings_survive():
    # manifest: 020
    # manifest: REQ-2
    # manifest: S10g.1
    # manifest: S10g.2
    # Verify legacy bindings survive (REQ-2) -- Expected: max absolute diff >= 150 at 90 and 180
    img = render_face(1024)
    pixels = img.load()
    R = 406
    cx, cy = 512, 512
    
    angles = [45, 90, 135, 180, 225, 315]
    
    for angle_deg in angles:
        rad = math.radians(angle_deg)
        has_dark = False
        has_bright = False
        
        # S10g.1: sampling every 2 px within [1.035 R, 1.24 R]
        # assert every listed angle carries >=1 sample with channel mean < 100 and >=1 with > 200
        start_px = math.ceil(1.035 * R)
        end_px = int(1.24 * R)
        
        prev_val = None
        max_diff = 0
        
        for r in range(start_px, end_px + 1, 2):
            x = int(cx + r * math.cos(rad))
            y = int(cy - r * math.sin(rad))
            val = sum(pixels[x, y][:3]) / 3
            
            if val < 100: has_dark = True
            if val > 200: has_bright = True
                
            if prev_val is not None:
                diff = abs(val - prev_val)
                if diff > max_diff:
                    max_diff = diff
            prev_val = val
            
        assert has_dark, f"No dark sample (<100) at angle {angle_deg}"
        assert has_bright, f"No bright sample (>200) at angle {angle_deg}"
        
        # S10g.2: at 90° and 180° assert the maximum absolute difference between adjacent samples is >= 150
        if angle_deg in [90, 180]:
            assert max_diff >= 150, f"Max adjacent 2px difference {max_diff} < 150 at angle {angle_deg}"
