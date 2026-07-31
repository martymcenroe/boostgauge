"""Core gauge entry point and routing module.

Issue #1: Core Gauge Renderer — Analog Tachometer.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import PIL.Image

from boostgauge.skins.stingray import render_stingray

_SKIN_REGISTRY = {
    "stingray": render_stingray,
}

def _get_skin(name: str):
    if name not in _SKIN_REGISTRY:
        raise ValueError(f"Unknown skin: {name!r}")
    return _SKIN_REGISTRY[name]

def validate_render_inputs(
    value: float,
    size: int,
) -> Tuple[float, int]:
    """Validate and clamp input metric value to [0.0, 100.0] and size to minimum 128 px."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"value must be float or int, got {type(value).__name__}")
    if not isinstance(size, (int, float)):
        raise TypeError(f"size must be integer, got {type(size).__name__}")

    clamped_value = max(0.0, min(100.0, float(value)))
    clamped_size = max(128, int(size))
    return clamped_value, clamped_size

def render(
    value: float,
    telltales=None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> PIL.Image.Image:
    """Render gauge state into off-screen PIL Image using configured skin (defaults to Stingray)."""
    clamped_val, clamped_sz = validate_render_inputs(value, size)

    skin_name = "stingray"
    if config and isinstance(config, dict) and "skin" in config:
        skin_name = str(config["skin"])

    renderer = _get_skin(skin_name)
    return renderer(clamped_val, telltales, clamped_sz, config)