"""Core gauge renderer entry point.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

from typing import Any
from PIL import Image

from boostgauge.skins.stingray import render_stingray

SUPPORTED_SKINS = {
    "stingray": render_stingray,
}


def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
    if size[0] < 128 or size[1] < 128:
        raise ValueError(f"Gauge size must be at least 128x128 pixels, got {size}")

    cfg = config or {}
    skin_name = cfg.get("skin", "stingray")

    if skin_name not in SUPPORTED_SKINS:
        raise ValueError(f"Unsupported skin: '{skin_name}'. Available skins: {sorted(SUPPORTED_SKINS.keys())}")

    clamped_value = max(0.0, min(100.0, float(value)))

    renderer = SUPPORTED_SKINS[skin_name]
    return renderer(value=clamped_value, telltales=telltales, size=size, config=cfg)