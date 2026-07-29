"""Core off-screen gauge renderer entry point.

Exposes pure `render()` pure function and input validation, routing rendering
requests to configured skin renderer (defaults to Stingray).

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple
from PIL import Image

from boostgauge.skins import get_skin_renderer
from boostgauge.skins.stingray import TelltaleDict


def validate_render_inputs(
    value: float,
    size: int,
) -> Tuple[float, int]:
    """Validate and clamp scalar metric value to [0.0, 100.0] and canvas size to minimum 128 px."""
    try:
        val_float = float(value)
        if math.isnan(val_float):
            clamped_val = 0.0
        else:
            clamped_val = max(0.0, min(100.0, val_float))
    except (ValueError, TypeError):
        clamped_val = 0.0

    try:
        size_int = int(size)
        clamped_size = max(128, min(1024, size_int))
    except (ValueError, TypeError):
        clamped_size = 256

    return clamped_val, clamped_size


def render(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Render gauge state into off-screen PIL Image using configured skin (defaults to Stingray).

    Args:
        value: Scalar metric value (0.0 to 100.0). Clamped to bounds if out of range.
        telltales: Optional dictionary mapping telltale window keys ('m1', 'm10', 'h1', 'all')
                   to peak float values (0.0 to 100.0) or None.
        size: Desired square image size in pixels (minimum 128 px, default 256 px).
        config: Optional configuration dictionary containing skin selection or overrides.

    Returns:
        PIL.Image.Image instance containing rendered gauge bitmap in RGBA mode.
    """
    clamped_val, clamped_size = validate_render_inputs(value, size)

    skin_name = "stingray"
    if config and isinstance(config, dict) and "skin" in config:
        skin_name = str(config["skin"])

    renderer = get_skin_renderer(skin_name)
    return renderer(value=clamped_val, telltales=telltales, size=clamped_size, config=config)