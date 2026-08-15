"""Main gauge orchestration module.

Issue #1: Feature: core gauge renderer
"""

from typing import TypedDict
from PIL import Image
from boostgauge.skins.stingray import render_skin

class SkinConfig(TypedDict):
    skin_name: str

def _validate_inputs(value: float, size: int) -> None:
    """Validates bounds of metric value and gauge size."""
    if not (0 <= value <= 100):
        raise ValueError(f"Value must be between 0 and 100, got {value}")
    if size < 128:
        raise ValueError(f"Size must be at least 128, got {size}")

def render(value: float, telltales: list[float | None], size: int = 256, config: dict = None) -> Image.Image:
    """Orchestrates rendering by delegating to the active skin."""
    _validate_inputs(value, size)

    if config is None:
        config = {"skin_name": "stingray"}

    if config.get("skin_name") == "stingray":
        return render_skin(value, telltales, size)

    raise ValueError(f"Unknown skin: {config.get('skin_name')}")