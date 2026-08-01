"""Main entry point for BoostGauge application.

Issue #7: Configuration File and CLI Arguments
"""

import sys
from typing import List, Optional

from boostgauge.config import ConfigManager, WindowPosition


def main(args_list: Optional[List[str]] = None) -> int:
    """Main application entry point integrating configuration, CLI parsing, and exit geometry persistence."""
    try:
        config_manager = ConfigManager(cli_args=args_list)
    except ValueError as err:
        print(f"Configuration Error: {err}", file=sys.stderr)
        return 1

    config = config_manager.config
    config_manager.save_geometry(config.position, config.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())