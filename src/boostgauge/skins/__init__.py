"""Skins package initialization and skin registry.

Issue #1: Core Gauge Renderer
Issue #45: Skin Protocol Specification
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional
from PIL import Image

from boostgauge.skins.stingray import render_stingray

# Skin registry mapping skin identifiers to rendering functions
SKIN_REGISTRY: Dict[str, Callable[..., Image.Image]] = {
    "stingray": render_stingray,
}

__all__ = ["SKIN_REGISTRY", "render_stingray"]