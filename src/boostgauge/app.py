"""Application runtime controller integrating configuration lifecycle.

Issue #5: always-on-top window with drag, minimize, and transparency (#5)
"""

from __future__ import annotations

import sys
from typing import Optional

from boostgauge.config import (
    ConfigError,
    apply_cli_overrides,
    get_default_config,
    get_default_config_path,
    load_config,
    parse_cli_args,
    save_config,
    update_window_geometry,
    validate_config,
)
from boostgauge.window import GaugeWindow
from boostgauge.tray import TrayManager, determine_tray_status


def main(args: Optional[list[str]] = None) -> int:
    """Execute main application startup sequence and configuration lifecycle."""
    try:
        parsed_args = parse_cli_args(args)
        target_config_path = parsed_args.config if parsed_args.config else get_default_config_path()

        if parsed_args.reset_config:
            default_config = get_default_config()
            save_config(default_config, target_config_path)
            config = default_config
        else:
            config = load_config(target_config_path)

        config = apply_cli_overrides(config, parsed_args)
        config = validate_config(config)

        window = GaugeWindow(config=config)

        def on_restore() -> None:
            window.root.after(0, window.restore_from_tray)

        def on_quit() -> None:
            def _shutdown() -> None:
                nonlocal config
                config = update_window_geometry(config, window.x, window.y, window.size)
                try:
                    save_config(config, target_config_path)
                except Exception:
                    pass
                tray.stop()
                window.destroy()
                window.root.quit()
            window.root.after(0, _shutdown)

        def on_toggle_topmost() -> None:
            window.root.after(0, window.toggle_topmost)

        tray = TrayManager(
            on_restore=on_restore,
            on_quit=on_quit,
            on_toggle_topmost=on_toggle_topmost,
        )
        tray.start()

        window.root.protocol("WM_DELETE_WINDOW", lambda: window.minimize_to_tray())
        window.root.mainloop()

        return 0

    except ConfigError as exc:
        print(f"BoostGauge Configuration Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())