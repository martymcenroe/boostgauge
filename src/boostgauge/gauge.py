"""Core tachometer gauge entry point exposing pure function `render()`.

Issue #1: Feature: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from typing import Any, Dict, Optional, Tuple
from PIL import Image

from boostgauge.skins.stingray import render_stingray


def _validate_render_args(
    value: float,
    size: Tuple[int, int],
    config: Optional[Dict[str, Any]],
) -> Tuple[float, Tuple[int, int]]:
    """Validate metric value bounds (clamped 0-100) and target image dimensions (minimum 128x128)."""
    if size[0] < 128 or size[1] < 128:
        raise ValueError(f"Gauge size must be at least 128x128 pixels, got {size}")

    clamped_value = max(0.0, min(100.0, float(value)))
    return clamped_value, size


def render(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: Tuple[int, int] = (256, 256),
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
    cfg = config or {}
    clamped_val, validated_size = _validate_render_args(value, size, cfg)

    skin = cfg.get("skin", "stingray")
    if skin == "stingray":
        return render_stingray(clamped_val, telltales=telltales, size=validated_size, config=cfg)
    else:
        raise ValueError(f"Unsupported skin: {skin}")