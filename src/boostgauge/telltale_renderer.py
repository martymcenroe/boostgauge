"""Telltale needle configuration, state manager, position mapping, and PIL renderer.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from boostgauge.telltale import Telltale


@dataclass(frozen=True)
class TelltaleStyle:
    """Style attributes for a single telltale window needle."""

    window_name: str
    window_seconds: Optional[float]
    color_rgba: Tuple[int, int, int, int]
    width_px: int
    dash_pattern: Optional[Tuple[int, int]]
    legend_label: str


@dataclass(frozen=True)
class GaugeGeometry:
    """Geometry parameters for needle angle and position calculation."""

    center_x: float
    center_y: float
    radius: float
    start_angle_deg: float = 225.0
    end_angle_deg: float = -45.0
    min_value: float = 0.0
    max_value: float = 100.0


DEFAULT_TELLTALE_STYLES: List[TelltaleStyle] = [
    TelltaleStyle(
        window_name="1m",
        window_seconds=60.0,
        color_rgba=(0, 220, 255, 160),
        width_px=2,
        dash_pattern=None,
        legend_label="1m",
    ),
    TelltaleStyle(
        window_name="10m",
        window_seconds=600.0,
        color_rgba=(255, 165, 0, 160),
        width_px=2,
        dash_pattern=None,
        legend_label="10m",
    ),
    TelltaleStyle(
        window_name="1h",
        window_seconds=3600.0,
        color_rgba=(220, 0, 220, 160),
        width_px=2,
        dash_pattern=(4, 4),
        legend_label="1h",
    ),
    TelltaleStyle(
        window_name="all_time",
        window_seconds=None,
        color_rgba=(255, 50, 50, 220),
        width_px=1,
        dash_pattern=None,
        legend_label="All",
    ),
]


def val_to_angle_rad(
    val: float,
    min_val: float = 0.0,
    max_val: float = 100.0,
    start_angle_deg: float = 225.0,
    end_angle_deg: float = -45.0,
) -> float:
    """Map a metric value deterministically to an angle in radians with NaN/Inf bounds checking."""
    if math.isnan(val):
        return math.radians(start_angle_deg)
    if val == float("inf"):
        clamped_val = max_val
    elif val == float("-inf"):
        clamped_val = min_val
    else:
        clamped_val = max(min_val, min(max_val, float(val)))

    val_range = max_val - min_val
    if val_range <= 0:
        norm = 0.0
    else:
        norm = (clamped_val - min_val) / val_range

    sweep_deg = end_angle_deg - start_angle_deg
    angle_deg = start_angle_deg + norm * sweep_deg
    return math.radians(angle_deg)


class TelltaleManager:
    """Manages four Telltale logic instances for 1m, 10m, 1h, and all-time windows."""

    def __init__(self, windows: Optional[Dict[str, Optional[float]]] = None) -> None:
        """Initialize the four Telltale instances with window bounds."""
        if windows is None:
            windows = {
                "1m": 60.0,
                "10m": 600.0,
                "1h": 3600.0,
                "all_time": None,
            }
        self.telltales: Dict[str, Telltale] = {}
        for name, win in windows.items():
            win_val = win if win is not None else float("inf")
            self.telltales[name] = Telltale(window=win_val)

    def update(self, timestamp: float, value: float) -> None:
        """Pipe a new metric sample into all four Telltale instances."""
        for telltale in self.telltales.values():
            telltale.update(timestamp, value)

    def reset(self, window_name: Optional[str] = None) -> None:
        """Reset a specific telltale by name, or all four if window_name is None."""
        if window_name is None:
            for telltale in self.telltales.values():
                telltale.reset()
        else:
            if window_name not in self.telltales:
                raise KeyError(f"Unknown window: {window_name}")
            self.telltales[window_name].reset()

    def get_peaks(self, current_time: Optional[float] = None) -> Dict[str, Optional[float]]:
        """Return a mapping of window_name to current peak value (or None)."""
        peaks: Dict[str, Optional[float]] = {}
        for name, telltale in self.telltales.items():
            peaks[name] = telltale.current_peak(current_time=current_time)
        return peaks


class TelltaleRenderer:
    """Renders telltale needles and legend onto a PIL Image gauge background surface."""

    def __init__(
        self,
        geometry: GaugeGeometry,
        styles: Optional[List[TelltaleStyle]] = None,
        show_legend: bool = True,
    ) -> None:
        """Initialize renderer with gauge geometry and telltale style definitions."""
        self.geometry = geometry
        self.styles = styles if styles is not None else DEFAULT_TELLTALE_STYLES
        self.show_legend = show_legend

    def render_telltales(
        self,
        base_image: Image.Image,
        peaks: Dict[str, Optional[float]],
    ) -> Image.Image:
        """Composite telltale needles onto base_image RGBA surface behind main needle."""
        if base_image.mode != "RGBA":
            raise ValueError("base_image must be RGBA mode")

        canvas = base_image.copy()
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        center_x = self.geometry.center_x
        center_y = self.geometry.center_y
        needle_length = self.geometry.radius * 0.85

        for style in self.styles:
            peak_val = peaks.get(style.window_name)
            if peak_val is None or math.isnan(peak_val):
                continue

            angle_rad = val_to_angle_rad(
                val=peak_val,
                min_val=self.geometry.min_value,
                max_val=self.geometry.max_value,
                start_angle_deg=self.geometry.start_angle_deg,
                end_angle_deg=self.geometry.end_angle_deg,
            )

            tip_x = center_x + needle_length * math.cos(angle_rad)
            tip_y = center_y - needle_length * math.sin(angle_rad)

            if style.dash_pattern is not None:
                self._draw_dashed_line(
                    draw=draw,
                    start=(center_x, center_y),
                    end=(tip_x, tip_y),
                    color=style.color_rgba,
                    width=style.width_px,
                    dash_pattern=style.dash_pattern,
                )
            else:
                draw.line(
                    [(center_x, center_y), (tip_x, tip_y)],
                    fill=style.color_rgba,
                    width=style.width_px,
                )

        composited = Image.alpha_composite(canvas, overlay)

        if self.show_legend:
            composited = self.render_legend(composited)

        return composited

    def _draw_dashed_line(
        self,
        draw: ImageDraw.ImageDraw,
        start: Tuple[float, float],
        end: Tuple[float, float],
        color: Tuple[int, int, int, int],
        width: int,
        dash_pattern: Tuple[int, int],
    ) -> None:
        """Draw a dashed line segment between start and end coordinates."""
        on_px, off_px = dash_pattern
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = math.hypot(dx, dy)
        if dist == 0:
            return

        ux = dx / dist
        uy = dy / dist
        step = on_px + off_px
        curr = 0.0

        while curr < dist:
            segment_end = min(curr + on_px, dist)
            p1 = (start[0] + ux * curr, start[1] + uy * curr)
            p2 = (start[0] + ux * segment_end, start[1] + uy * segment_end)
            draw.line([p1, p2], fill=color, width=width)
            curr += step

    def render_legend(self, base_image: Image.Image) -> Image.Image:
        """Render small color-coded telltale legend overlay in bottom-left corner."""
        if base_image.mode != "RGBA":
            canvas = base_image.convert("RGBA")
        else:
            canvas = base_image.copy()

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        margin_x = 10
        margin_y = canvas.height - 50
        box_width = 75
        box_height = 40

        draw.rectangle(
            [margin_x, margin_y, margin_x + box_width, margin_y + box_height],
            fill=(20, 22, 28, 180),
            outline=(60, 65, 75, 200),
            width=1,
        )

        font = ImageFont.load_default()
        item_y = margin_y + 4

        for style in self.styles[:4]:
            draw.rectangle(
                [margin_x + 6, item_y + 2, margin_x + 14, item_y + 8],
                fill=style.color_rgba,
            )
            draw.text(
                (margin_x + 18, item_y - 1),
                style.legend_label,
                fill=(220, 225, 230, 240),
                font=font,
            )
            item_y += 9

        return Image.alpha_composite(canvas, overlay)