"""Public entry point facade for BoostGauge renderer.

Issue #1: Core gauge renderer — analog tachometer with arc, needle, and tick marks
"""

from typing import Any, Dict, Optional
from PIL import Image

from boostgauge.skins import get_skin

MIN_GAUGE_SIZE = 128
DEFAULT_GAUGE_SIZE = 256


def render(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: int = DEFAULT_GAUGE_SIZE,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Public entry point for off-screen gauge rendering.

    Validates inputs, clamps metric value to [0.0, 100.0], dispatches to configured
    skin renderer, and returns a rendered PIL.Image object.

    Args:
        value: Metric value to display on gauge scale (0.0 to 100.0).
        telltales: Optional dict of peak-hold window values ('m1', 'm10', 'h1', 'all_time').
        size: Target image width and height in pixels (must be >= 128).
        config: Optional configuration dictionary containing skin choice.

    Returns:
        PIL.Image.Image: Rendered RGBA image of size (size, size).

    Raises:
        TypeError: If `value` is not an int or float.
        ValueError: If `size` < 128 or requested skin name is unregistered.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"Value must be a numeric float or int, got {type(value).__name__}")

    if not isinstance(size, int) or size < MIN_GAUGE_SIZE:
        raise ValueError(f"Gauge size must be an integer >= {MIN_GAUGE_SIZE}, got {size}")

    clamped_value = max(0.0, min(100.0, float(value)))

    cfg = config or {}
    skin_name = cfg.get("skin", "stingray")

    skin_renderer = get_skin(skin_name)
    return skin_renderer(
        value=clamped_value,
        telltales=telltales,
        size=size,
        config=cfg,
    )