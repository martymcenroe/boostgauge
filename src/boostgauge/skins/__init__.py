"""Skins package for boostgauge renderers.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks.
"""

from __future__ import annotations

from typing import Any, Dict, Callable, Optional, TypedDict
import PIL.Image

class TelltaleDict(TypedDict, total=False):
    """Peak-hold values for 1m, 10m, 1h, and all-time windows."""
    m1: Optional[float]
    m10: Optional[float]
    h1: Optional[float]
    all: Optional[float]

SkinRenderer = Callable[[float, Any, int, Any], PIL.Image.Image]

from boostgauge.skins.stingray import render_stingray, StingraySkin

SKIN_REGISTRY: Dict[str, SkinRenderer] = {
    "stingray": render_stingray,
}

def get_skin(name: str = "stingray") -> SkinRenderer:
    """Retrieve skin renderer by name from registry."""
    if name not in SKIN_REGISTRY:
        raise ValueError(f"Unknown skin: {name!r}. Available skins: {list(SKIN_REGISTRY.keys())}")
    return SKIN_REGISTRY[name]

__all__ = [
    "SKIN_REGISTRY",
    "StingraySkin",
    "TelltaleDict",
    "get_skin",
    "render_stingray",
]