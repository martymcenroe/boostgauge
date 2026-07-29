"""Skins package for BoostGauge tachometer renderers.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
Issue #45: Plugin Skin Registry Protocol
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional
from PIL import Image

from boostgauge.skins.stingray import render_stingray, SkinProtocol

# Skin registry mapping skin name to renderer callable
SKIN_REGISTRY: Dict[str, Callable[..., Image.Image]] = {
    "stingray": render_stingray,
}


def get_skin_renderer(name: str = "stingray") -> Callable[..., Image.Image]:
    """Retrieve skin rendering function by name, falling back to 'stingray' if unknown."""
    return SKIN_REGISTRY.get(name.lower(), render_stingray)


__all__ = ["SKIN_REGISTRY", "get_skin_renderer", "SkinProtocol", "render_stingray"]