"""Telltale needle configuration, management, and off-screen Pillow rendering.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from boostgauge.telltale import Telltale

logger = logging.getLogger(__name__)


def val_to_angle_rad(
    value: float,
    min_val: float = 0.0,
    max_val: float = 100.0,
    start_angle_deg: float = 135.0,
    end_angle_deg: float = 405.0,
) -> float:
    """Map metric value to polar angle in radians."""
    if not math.isfinite(value):
        return math.radians(start_angle_deg)
    if max_val <= min_val:
        return math.radians(start_angle_deg)
    clamped = max(min_val, min(max_val, value))
    fraction = (clamped - min_val) / (max_val - min_val)
    return math.radians(start_angle_deg + fraction * (end_angle_deg - start_angle_deg))


@dataclass(frozen=True)
class TelltaleStyle:
    """Visual style specification for a telltale needle."""

    window_name: str
    window_seconds: Optional[float]
    color_rgba: Tuple[int, int, int, int]
    width_px: int
    is_dashed: bool
    legend_label: str


@dataclass(frozen=True)
class GaugeGeometry:
    """Gauge geometry for radial angle mapping."""

    center_x: float = 128.0
    center_y: float = 128.0
    radius: float = 100.0
    start_angle_deg: float = 135.0
    end_angle_deg: float = 405.0
    min_value: float = 0.0
    max_value: float = 100.0


TELLTALE_CONFIGS: Dict[str, TelltaleStyle] = {
    "1m": TelltaleStyle(
        window_name="1m",
        window_seconds=60.0,
        color_rgba=(0, 255, 255, 180),
        width_px=2,
        is_dashed=False,
        legend_label="1m Peak",
    ),
    "10m": TelltaleStyle(
        window_name="10m",
        window_seconds=600.0,
        color_rgba=(255, 140, 0, 180),
        width_px=2,
        is_dashed=False,
        legend_label="10m Peak",
    ),
    "1h": TelltaleStyle(
        window_name="1h",
        window_seconds=3600.0,
        color_rgba=(255, 0, 255, 200),
        width_px=2,
        is_dashed=True,
        legend_label="1h Peak",
    ),
    "all_time": TelltaleStyle(
        window_name="all_time",
        window_seconds=None,
        color_rgba=(255, 0, 0, 255),
        width_px=2,
        is_dashed=False,
        legend_label="All-Time Peak",
    ),
}

_DEFAULT_WINDOWS: Dict[str, Optional[float]] = {
    "1m": 60.0,
    "10m": 600.0,
    "1h": 3600.0,
    "all_time": None,
}


class _SlidingWindowPeak:
    """Sliding window peak tracker that keeps all samples and prunes on query."""

    def __init__(self, window_seconds: Optional[float]) -> None:
        self._window = window_seconds
        self._samples: list = []  # list of (timestamp, value)

    def update(self, timestamp: float, value: float) -> None:
        self._samples.append((timestamp, value))

    def current_peak(self, current_time: Optional[float] = None) -> Optional[float]:
        if not self._samples:
            return None
        if current_time is None or self._window is None:
            return max(v for _, v in self._samples)
        cutoff = current_time - self._window
        in_window = [v for t, v in self._samples if t >= cutoff]
        if in_window:
            return max(in_window)
        # All samples expired: return the most recent value observed
        return self._samples[-1][1]

    def reset(self) -> None:
        self._samples = []


class TelltaleManager:
    """Dispatches metric updates to 1m, 10m, 1h, and all-time peak trackers."""

    def __init__(self, custom_windows: Optional[Dict[str, Optional[float]]] = None) -> None:
        windows = custom_windows if custom_windows is not None else dict(_DEFAULT_WINDOWS)
        self.telltales: Dict[str, _SlidingWindowPeak] = {
            name: _SlidingWindowPeak(win_sec) for name, win_sec in windows.items()
        }

    def update(self, timestamp: float, value: float) -> None:
        """Pipe timestamp and metric value into all telltale trackers."""
        if not math.isfinite(value):
            logger.warning("[TelltaleManager] Ignored non-finite metric value: %s", value)
            return
        if not math.isfinite(timestamp):
            logger.warning("[TelltaleManager] Ignored non-finite timestamp: %s", timestamp)
            return
        for tracker in self.telltales.values():
            tracker.update(timestamp, value)

    def current_peaks(self, current_time: Optional[float] = None) -> Dict[str, Optional[float]]:
        """Return mapping of window names to current peak values (or None)."""
        return {name: t.current_peak(current_time) for name, t in self.telltales.items()}

    def reset(self, window_name: Optional[str] = None) -> None:
        """Reset named window, or all windows when window_name is None."""
        if window_name is None:
            for tracker in self.telltales.values():
                tracker.reset()
        elif window_name in self.telltales:
            self.telltales[window_name].reset()
        else:
            raise KeyError(f"Unknown window name: {window_name}")


class TelltaleRenderer:
    """Renders telltale needles and legend onto a PIL.Image gauge surface."""

    def __init__(self, geometry: Optional[GaugeGeometry] = None) -> None:
        self.geometry = geometry if geometry is not None else GaugeGeometry()

    def render_telltales(
        self,
        base_image: Image.Image,
        peaks: Dict[str, Optional[float]],
        render_legend: bool = False,
    ) -> Image.Image:
        """Alpha composite telltale needle layer onto base gauge surface."""
        base_rgba = base_image.convert("RGBA")
        has_any_peak = any(v is not None for v in peaks.values())

        overlay = self._build_needle_layer(peaks, base_rgba.size)
        result = Image.alpha_composite(base_rgba, overlay)

        if render_legend and has_any_peak:
            result = self._draw_legend(result)

        return result

    def _build_needle_layer(
        self, peaks: Dict[str, Optional[float]], canvas_size: Tuple[int, int]
    ) -> Image.Image:
        overlay = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        cx = self.geometry.center_x
        cy = self.geometry.center_y
        needle_r = self.geometry.radius * 0.85

        for name, style in TELLTALE_CONFIGS.items():
            peak_val = peaks.get(name)
            if peak_val is None:
                continue

            angle_rad = val_to_angle_rad(
                peak_val,
                self.geometry.min_value,
                self.geometry.max_value,
                self.geometry.start_angle_deg,
                self.geometry.end_angle_deg,
            )
            x2 = cx + needle_r * math.cos(angle_rad)
            y2 = cy + needle_r * math.sin(angle_rad)

            if style.is_dashed:
                self._draw_dashed_line(draw, (cx, cy), (x2, y2), style.color_rgba, style.width_px)
            else:
                draw.line(
                    [(cx, cy), (x2, y2)],
                    fill=style.color_rgba,
                    width=style.width_px,
                )

        return overlay

    def _draw_dashed_line(
        self,
        draw: ImageDraw.ImageDraw,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        color: Tuple[int, int, int, int],
        width: int,
        dash_len: float = 4.0,
        gap_len: float = 3.0,
    ) -> None:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        ux, uy = dx / dist, dy / dist
        curr = 0.0
        while curr < dist:
            end = min(curr + dash_len, dist)
            draw.line(
                [
                    (p1[0] + ux * curr, p1[1] + uy * curr),
                    (p1[0] + ux * end, p1[1] + uy * end),
                ],
                fill=color,
                width=width,
            )
            curr = end + gap_len

    def _draw_legend(self, image: Image.Image) -> Image.Image:
        result = image.copy()
        draw = ImageDraw.Draw(result)
        font = ImageFont.load_default()

        x, y = 10, 10
        line_height = 14
        swatch = 10

        for name, style in TELLTALE_CONFIGS.items():
            draw.rectangle(
                [x, y + 2, x + swatch, y + 2 + swatch],
                fill=style.color_rgba,
                outline=(255, 255, 255, 220),
            )
            draw.text(
                (x + swatch + 6, y),
                f"{name}: {style.legend_label}",
                fill=(230, 230, 230, 255),
                font=font,
            )
            y += line_height

        return result