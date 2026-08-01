"""Telltale needle configuration, manager, position mapping, and PIL image drawing logic.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple, TypedDict

from PIL import Image, ImageDraw


class _Telltale:
    """Peak-hold tracker over an optional sliding time window."""

    def __init__(self, window: Optional[float] = None) -> None:
        self._window = window
        self._samples: List[Tuple[float, float]] = []

    def update(self, timestamp: float, value: float) -> None:
        self._samples.append((timestamp, value))

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        if not self._samples:
            return None
        if self._window is None or timestamp is None:
            return max(v for _, v in self._samples)
        cutoff = timestamp - self._window
        relevant = [v for t, v in self._samples if t >= cutoff]
        if not relevant:
            return None
        return max(relevant)

    def reset(self) -> None:
        self._samples.clear()


@dataclass(frozen=True)
class TelltaleStyle:
    """Visual style specification for a telltale window needle."""

    window_name: str
    window_seconds: Optional[float]
    color: Tuple[int, int, int, int]
    width: int
    line_style: str
    description: str


class TelltaleState(TypedDict):
    """Runtime state dictionary representation for a telltale needle."""

    window_name: str
    current_peak: Optional[float]
    angle_rad: Optional[float]
    visible: bool


DEFAULT_TELLTALE_STYLES: Dict[str, TelltaleStyle] = {
    "1m": TelltaleStyle(
        window_name="1m",
        window_seconds=60.0,
        color=(0, 225, 255, 180),
        width=3,
        line_style="solid",
        description="1 Min Peak",
    ),
    "10m": TelltaleStyle(
        window_name="10m",
        window_seconds=600.0,
        color=(255, 140, 0, 180),
        width=3,
        line_style="solid",
        description="10 Min Peak",
    ),
    "1h": TelltaleStyle(
        window_name="1h",
        window_seconds=3600.0,
        color=(220, 0, 220, 180),
        width=3,
        line_style="solid",
        description="1 Hour Peak",
    ),
    "all_time": TelltaleStyle(
        window_name="all_time",
        window_seconds=None,
        color=(255, 40, 40, 180),
        width=3,
        line_style="solid",
        description="All-Time Peak",
    ),
}


class TelltaleManager:
    """Manages Telltale instances for peak tracking across configurable time windows."""

    def __init__(
        self,
        custom_windows: Optional[Dict[str, Optional[float]]] = None,
    ) -> None:
        """Initialize Telltale instances for 1m, 10m, 1h, and all-time windows."""
        if custom_windows is None:
            self._window_configs: Dict[str, Optional[float]] = {
                "1m": 60.0,
                "10m": 600.0,
                "1h": 3600.0,
                "all_time": None,
            }
        else:
            self._window_configs = dict(custom_windows)

        self.telltales: Dict[str, _Telltale] = {}
        for name, window_sec in self._window_configs.items():
            if window_sec is not None and window_sec <= 0:
                raise ValueError(
                    f"Window seconds must be positive or None, got {window_sec}"
                )
            self.telltales[name] = _Telltale(window=window_sec)

    def update(self, timestamp: float, value: float) -> None:
        """Forward sample (timestamp, value) to all managed telltale instances."""
        sanitized_val = max(0.0, min(100.0, float(value)))
        for telltale in self.telltales.values():
            telltale.update(timestamp, sanitized_val)

    def reset_window(self, window_name: str) -> None:
        """Reset peak state for a specific window by name."""
        if window_name not in self.telltales:
            raise KeyError(f"Unknown telltale window: '{window_name}'")
        self.telltales[window_name].reset()

    def reset_all(self) -> None:
        """Reset peak state for all managed telltales."""
        for telltale in self.telltales.values():
            telltale.reset()

    def get_peaks(self, timestamp: Optional[float] = None) -> Dict[str, Optional[float]]:
        """Return current peak values for all registered window names."""
        return {
            name: telltale.current_peak(timestamp)
            for name, telltale in self.telltales.items()
        }


class TelltaleRenderer:
    """Renders telltale needles and legend onto PIL Image surface."""

    def __init__(
        self,
        min_val: float = 0.0,
        max_val: float = 100.0,
        min_angle_deg: float = 225.0,
        max_angle_deg: float = -45.0,
        styles: Optional[Dict[str, TelltaleStyle]] = None,
    ) -> None:
        """Initialize angular range parameters and visual styles."""
        self.min_val = min_val
        self.max_val = max_val
        self.min_angle_deg = min_angle_deg
        self.max_angle_deg = max_angle_deg
        self.styles = styles if styles is not None else DEFAULT_TELLTALE_STYLES

    def val_to_angle_rad(self, value: float) -> float:
        """Map metric value (0-100) to gauge sweep angle in radians."""
        if math.isnan(value):
            value = self.min_val
        clamped_val = max(self.min_val, min(self.max_val, value))
        val_range = self.max_val - self.min_val
        if val_range == 0:
            fraction = 0.0
        else:
            fraction = (clamped_val - self.min_val) / val_range
        angle_deg = self.min_angle_deg + fraction * (self.max_angle_deg - self.min_angle_deg)
        return math.radians(angle_deg)

    def draw_telltales(
        self,
        image: Image.Image,
        peaks: Dict[str, Optional[float]],
        center: Tuple[float, float],
        radius: float,
        supersample_factor: int = 4,
    ) -> Image.Image:
        """Draw active translucent telltale needles onto an offscreen RGBA overlay layer."""
        if image.mode != "RGBA":
            base_image = image.convert("RGBA")
        else:
            base_image = image

        overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        cx, cy = center
        z_order = ["all_time", "1h", "10m", "1m"]
        for window_name in z_order:
            peak_val = peaks.get(window_name)
            if peak_val is None:
                continue

            style = self.styles.get(window_name)
            if style is None:
                continue

            angle_rad = self.val_to_angle_rad(peak_val)
            tip_x = cx + radius * math.cos(angle_rad)
            tip_y = cy - radius * math.sin(angle_rad)

            line_width = max(1, style.width * supersample_factor // 4)
            draw.line(
                [(cx, cy), (tip_x, tip_y)],
                fill=style.color,
                width=line_width,
            )

        return Image.alpha_composite(base_image, overlay)

    def draw_legend(
        self,
        image: Image.Image,
        peaks: Dict[str, Optional[float]],
        origin: Tuple[float, float],
        supersample_factor: int = 4,
    ) -> Image.Image:
        """Render color-coded legend showing window status in gauge corner."""
        if image.mode != "RGBA":
            base_image = image.convert("RGBA")
        else:
            base_image = image

        overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        ox, oy = origin
        box_size = 12 * supersample_factor // 4
        spacing = 18 * supersample_factor // 4

        curr_y = oy
        for name, style in self.styles.items():
            peak_val = peaks.get(name)
            fill_color = style.color if peak_val is not None else (128, 128, 128, 100)

            draw.rectangle(
                [(ox, curr_y), (ox + box_size, curr_y + box_size)],
                fill=fill_color,
                outline=(255, 255, 255, 200),
            )
            curr_y += spacing

        return Image.alpha_composite(base_image, overlay)