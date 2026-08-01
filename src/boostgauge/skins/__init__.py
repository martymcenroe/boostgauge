"""Skins package for BoostGauge renderers.

Issue #1: Core gauge renderer — analog tachometer with arc, needle, and tick marks
"""

from typing import Any, Dict, Optional, Protocol
from PIL import Image

class GaugeSkin(Protocol):
    """Protocol for gauge skin renderers per Issue #45 extensibility design."""

    def __call__(
        self,
        value: float,
        telltales: Optional[Dict[str, Optional[float]]] = None,
        size: int = 256,
        config: Optional[Dict[str, Any]] = None,
    ) -> Image.Image:
        """Render skin to a PIL.Image instance."""
        ...

SKIN_REGISTRY: Dict[str, GaugeSkin] = {}

def register_skin(name: str, renderer: GaugeSkin) -> None:
    """Register a skin renderer callable under the given name."""
    SKIN_REGISTRY[name] = renderer

def get_skin(name: str = "stingray") -> GaugeSkin:
    """Look up a skin renderer callable by name.

    Raises:
        ValueError: If `name` is not present in SKIN_REGISTRY.
    """
    if name not in SKIN_REGISTRY:
        available = sorted(list(SKIN_REGISTRY.keys()))
        raise ValueError(f"Unknown skin: '{name}'. Available skins: {available}")
    return SKIN_REGISTRY[name]

# Ensure stingray skin is registered on module import
from . import stingray  # noqa: F401