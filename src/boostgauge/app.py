"""Main application entry point.

Issue #7: Feature: configuration file and CLI arguments
"""

import re
import sys
import tkinter as tk
from pathlib import Path

from boostgauge.config import (
    ConfigManager,
    get_default_config,
    get_default_config_path,
    parse_cli_args,
    save_config,
)


def main() -> None:
    """Bootstrap application execution flow."""
    cli_args = parse_cli_args()

    config_path = (
        Path(cli_args.config) if cli_args.config else get_default_config_path()
    )

    if cli_args.reset_config:
        try:
            default_conf = get_default_config()
            save_config(default_conf, config_path)
            print(f"Configuration successfully reset at: {config_path}")
            sys.exit(0)
        except Exception as e:
            print(
                f"Error resetting configuration file: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    config_mgr = ConfigManager(config_path=config_path, cli_args=cli_args)
    try:
        config_mgr.load()
    except Exception as e:
        print(f"Fatal error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)

    root = tk.Tk()
    root.title("BoostGauge")

    size = config_mgr.get("size")
    pos_x = config_mgr.get("position")["x"]
    pos_y = config_mgr.get("position")["y"]
    opacity = config_mgr.get("opacity")
    always_on_top = config_mgr.get("always_on_top")

    root.geometry(f"{size}x{size}+{pos_x}+{pos_y}")
    root.resizable(False, False)
    root.attributes("-alpha", opacity)
    root.attributes("-topmost", always_on_top)

    label = tk.Label(
        root,
        text=f"BoostGauge ({config_mgr.get('theme')})",
        font=("Arial", 12),
    )
    label.pack(expand=True)

    def poll_config_reload() -> None:
        if config_mgr.check_and_reload():
            root.attributes("-alpha", config_mgr.get("opacity"))
            root.attributes("-topmost", config_mgr.get("always_on_top"))
            label.config(text=f"BoostGauge ({config_mgr.get('theme')})")
        root.after(2000, poll_config_reload)

    def on_window_close() -> None:
        try:
            geometry_str = root.geometry()
            match = re.match(r"^(\d+)x(\d+)([-+]\d+)([-+]\d+)$", geometry_str)
            if match:
                width = int(match.group(1))
                x_coord = int(match.group(3))
                y_coord = int(match.group(4))
                config_mgr.update_position_and_size(x_coord, y_coord, width)
                config_mgr.save()
        except Exception as e:
            print(
                f"Warning: Failed to save position and size metrics on close: {e}",
                file=sys.stderr,
            )
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_window_close)
    root.after(2000, poll_config_reload)
    root.mainloop()


if __name__ == "__main__":
    main()