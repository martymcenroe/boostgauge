"""Core gauge entry point exposing pure render() function and skin routing.

Issue #1: Core Gauge Renderer
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from PIL import Image

from boostgauge.skins import SKIN_REGISTRY
from boostgauge.skins.stingray import TelltaleDict


def validate_render_inputs(
    value: float,
    size: int,
) -> Tuple[float, int]:
    """Validate and clamp input metric value to [0.0, 100.0] and size to minimum 128 px."""
    clamped_val = max(0.0, min(100.0, float(value)))
    clamped_size = max(128, int(size))
    return clamped_val, clamped_size


def render(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Render gauge state into off-screen PIL Image using configured skin (defaults to Stingray)."""
    clamped_val, clamped_size = validate_render_inputs(value, size)

    config_dict = config or {}
    skin_name = config_dict.get("skin", "stingray")

    renderer = SKIN_REGISTRY.get(skin_name)
    if renderer is None:
        raise ValueError(f"Unknown skin: '{skin_name}'. Available skins: {list(SKIN_REGISTRY.keys())}")

    return renderer(clamped_val, telltales=telltales, size=clamped_size, config=config_dict)