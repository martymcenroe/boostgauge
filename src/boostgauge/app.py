"""The window and the entry point (issue #5).

Frameless, always-on-top, draggable by the face, transparent outside the
housing's rounded square (``-transparentcolor``), wheel-resizable, opacity
from config with 100 % on hover, a hover tooltip naming the four telltale
windows (#2 U1), a right-click menu carrying #2's reset entries, and a
pystray tray icon whose dot is green / yellow / red for the composite value.
Position and size persist through #7's exit write.

Everything that can be pure lives in ``session.py`` and in the small pure
helpers at the top of this module, which the unit tier covers. ``tkinter``
is instantiated only inside ``App`` and ``main`` — never in tests
(docs/design/0001-test-strategy.md, Option C).
"""

from __future__ import annotations

import queue
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

from boostgauge.collector import CollectorThread, make_collector
from boostgauge.config import ConfigError, load_config, parse_cli, thresholds_from_config
from boostgauge.session import Session

TRANSPARENT_KEY = (1, 2, 3)          # a colour the face never paints; keyed out by the window manager
TRANSPARENT_HEX = "#010203"
CORNER_RATIO = 0.13                  # the housing's chamfer radius, S7 — matches skins/stingray
MIN_SIZE, MAX_SIZE = 100, 1200
REREAD_SECONDS = 5.0                 # #7 H1: threshold edits take effect without a restart
TOOLTIP_DELAY_MS = 600
GREEN, YELLOW, RED = (76, 175, 80), (255, 193, 7), (244, 67, 54)


# ---- pure helpers (unit-tested) -------------------------------------------------


def tray_color(value: float) -> tuple[int, int, int]:
    """Green below 60, yellow from 60, red from 80 — the composite's band boundaries (#4)."""
    if value >= 80:
        return RED
    if value >= 60:
        return YELLOW
    return GREEN


def tray_image(color: tuple[int, int, int], size: int = 64) -> Image.Image:
    """A filled dot on a transparent square, for the tray."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = size // 8
    d.ellipse([pad, pad, size - pad, size - pad], fill=color + (255,),
              outline=(20, 20, 22, 255), width=max(1, size // 32))
    return img


def keyed_frame(frame: Image.Image) -> Image.Image:
    """The frame with everything outside the housing's rounded square painted the key colour."""
    size = frame.width
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1],
                                           radius=int(CORNER_RATIO * size), fill=255)
    out = Image.new("RGB", (size, size), TRANSPARENT_KEY)
    out.paste(frame.convert("RGB"), (0, 0), mask)
    return out


def clamp_to_screen(x: int, y: int, size: int, screen_w: int, screen_h: int) -> tuple[int, int]:
    """Keep the window on a screen: if it would sit off-screen, bring it back to the edge."""
    x = max(0, min(int(x), max(0, screen_w - size)))
    y = max(0, min(int(y), max(0, screen_h - size)))
    return x, y


def step_size(size: int, direction: int) -> int:
    """Wheel resize: ±10 %, clamped, always square."""
    factor = 1.10 if direction > 0 else 1 / 1.10
    return max(MIN_SIZE, min(MAX_SIZE, int(round(size * factor))))


# ---- the window --------------------------------------------------------------------


class App:
    """The tkinter shell. Construct with a ready ``Session`` and a running collector thread."""

    def __init__(self, session: Session, collector_thread: CollectorThread) -> None:
        import tkinter as tk

        from PIL import ImageTk

        self.tk = tk
        self.ImageTk = ImageTk
        self.session = session
        self.collector_thread = collector_thread
        self.config = session.config
        self.size = int(self.config["size"])
        self.topmost = bool(self.config["always_on_top"])
        self.opacity = float(self.config["opacity"])
        self.interval_ms = max(100, int(float(self.config["polling_interval_seconds"]) * 1000))
        self._last_reread = time.monotonic()
        self._last_key = None
        self._drag_origin = None
        self._tooltip = None
        self._tooltip_job = None
        self._tray = None
        self._tray_color = None
        self._photo = None

        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:  # noqa: BLE001 — cosmetic on older Windows
                pass

        root = self.root = tk.Tk()
        root.title("boostgauge")
        root.overrideredirect(True)
        root.attributes("-topmost", self.topmost)
        root.attributes("-alpha", self.opacity)
        root.configure(bg=TRANSPARENT_HEX)
        if sys.platform == "win32":
            root.attributes("-transparentcolor", TRANSPARENT_HEX)

        pos = self.config["position"]
        x, y = clamp_to_screen(pos["x"], pos["y"], self.size,
                               root.winfo_screenwidth(), root.winfo_screenheight())
        root.geometry(f"{self.size}x{self.size}+{x}+{y}")

        self.label = tk.Label(root, bg=TRANSPARENT_HEX, bd=0, highlightthickness=0)
        self.label.pack(fill="both", expand=True)

        self.label.bind("<ButtonPress-1>", self._drag_start)
        self.label.bind("<B1-Motion>", self._drag_move)
        self.label.bind("<ButtonRelease-1>", self._drag_end)
        self.label.bind("<Button-3>", self._popup_menu)
        self.label.bind("<MouseWheel>", self._wheel)
        self.label.bind("<Enter>", self._hover_enter)
        self.label.bind("<Leave>", self._hover_leave)

        self._build_menu()
        self._start_tray()
        self._draw(force=True)
        root.after(self.interval_ms, self._tick)

    # ---- refresh loop ----------------------------------------------------------------
    def _tick(self) -> None:
        self.session.drain(self.collector_thread.snapshots)
        now = time.monotonic()
        if now - self._last_reread >= REREAD_SECONDS:
            self._last_reread = now
            self.session.reread_thresholds()
        self._draw()
        self._update_tray()
        self.root.after(self.interval_ms, self._tick)

    def _draw(self, force: bool = False) -> None:
        key = (round(self.session.value, 2), tuple(self.session.telltales.peaks()), self.size)
        if not force and key == self._last_key:
            return
        self._last_key = key
        frame = keyed_frame(self.session.frame(self.size))
        self._photo = self.ImageTk.PhotoImage(frame)
        self.label.configure(image=self._photo)

    # ---- drag ----------------------------------------------------------------------
    def _drag_start(self, event) -> None:
        self._drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_move(self, event) -> None:
        if self._drag_origin is None:
            return
        ox, oy = self._drag_origin
        self.root.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")

    def _drag_end(self, _event) -> None:
        if self._drag_origin is None:
            return
        self._drag_origin = None
        self.session.moved(self.root.winfo_x(), self.root.winfo_y())

    # ---- resize --------------------------------------------------------------------
    def _wheel(self, event) -> None:
        new = step_size(self.size, 1 if event.delta > 0 else -1)
        if new == self.size:
            return
        self.size = new
        self.session.resized(new)
        self.root.geometry(f"{new}x{new}")
        self._draw(force=True)

    # ---- hover: opacity + tooltip (#2 U1) -----------------------------------------------
    def _hover_enter(self, _event) -> None:
        self.root.attributes("-alpha", 1.0)
        self._tooltip_job = self.root.after(TOOLTIP_DELAY_MS, self._show_tooltip)

    def _hover_leave(self, _event) -> None:
        self.root.attributes("-alpha", self.opacity)
        if self._tooltip_job is not None:
            self.root.after_cancel(self._tooltip_job)
            self._tooltip_job = None
        self._hide_tooltip()

    def _show_tooltip(self) -> None:
        self._hide_tooltip()
        tip = self._tooltip = self.tk.Toplevel(self.root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        self.tk.Label(tip, text=self.session.telltales.tooltip_text(), justify="left",
                      bg="#1a1a1c", fg="#ffffff", padx=8, pady=6).pack()
        tip.geometry(f"+{self.root.winfo_x() + self.size + 8}+{self.root.winfo_y()}")

    def _hide_tooltip(self) -> None:
        if self._tooltip is not None:
            self._tooltip.destroy()
            self._tooltip = None

    # ---- context menu (#2 RS1-RS5) ---------------------------------------------------------
    def _build_menu(self) -> None:
        self.menu = self.tk.Menu(self.root, tearoff=0)
        for label, handler in self.session.telltales.menu_entries():
            self.menu.add_command(label=label, command=self._after_reset(handler))
        self.menu.add_separator()
        self._topmost_var = self.tk.BooleanVar(value=self.topmost)
        self.menu.add_checkbutton(label="Always on top", variable=self._topmost_var,
                                  command=self._toggle_topmost)
        self.menu.add_command(label="Minimize to tray", command=self.minimize)
        self.menu.add_separator()
        self.menu.add_command(label="Quit", command=self.quit)

    def _after_reset(self, handler):
        def run():
            handler()
            self._draw(force=True)
        return run

    def _popup_menu(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _toggle_topmost(self) -> None:
        self.topmost = bool(self._topmost_var.get())
        self.root.attributes("-topmost", self.topmost)

    # ---- tray ------------------------------------------------------------------------
    def _start_tray(self) -> None:
        try:
            import pystray
        except Exception:  # noqa: BLE001 — the gauge works without a tray
            return
        self._tray_color = tray_color(self.session.value)
        menu = pystray.Menu(
            pystray.MenuItem("Show", lambda: self.root.after(0, self.restore), default=True),
            pystray.MenuItem("Reset All", lambda: self.root.after(0, self._after_reset(
                self.session.telltales.reset_all))),
            pystray.MenuItem("Quit", lambda: self.root.after(0, self.quit)),
        )
        self._tray = pystray.Icon("boostgauge", tray_image(self._tray_color), "boostgauge", menu)
        self._tray.run_detached()

    def _update_tray(self) -> None:
        if self._tray is None:
            return
        color = tray_color(self.session.value)
        if color != self._tray_color:
            self._tray_color = color
            self._tray.icon = tray_image(color)

    def minimize(self) -> None:
        self._hide_tooltip()
        self.root.withdraw()

    def restore(self) -> None:
        self.root.deiconify()
        self.root.attributes("-topmost", self.topmost)

    # ---- lifecycle -------------------------------------------------------------------------
    def quit(self) -> None:
        self._hide_tooltip()
        try:
            self.collector_thread.stop(timeout=3.0)
        finally:
            self.session.exit_write()
            if self._tray is not None:
                try:
                    self._tray.stop()
                except Exception:  # noqa: BLE001
                    pass
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


# ---- entry point ------------------------------------------------------------------------


def main(argv=None) -> int:
    """``boostgauge [OPTIONS]`` — the console script. Returns the exit status."""
    path, reset_flag, overrides = parse_cli(argv)
    try:
        config = load_config(path, reset_flag=reset_flag, cli_overrides=overrides)
    except ConfigError as exc:
        print(f"boostgauge: {exc}", file=sys.stderr)
        return 2

    collector = make_collector(thresholds_from_config(config))
    thread = CollectorThread(collector, interval=float(config["polling_interval_seconds"]),
                             snapshots=queue.Queue())
    thread.start()
    session = Session(config, Path(path), collector=collector)
    App(session, thread).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
