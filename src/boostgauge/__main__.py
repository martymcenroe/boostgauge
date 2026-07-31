"""Main entry point execution for boostgauge CLI script.

Issue #7: Configuration File and CLI Arguments
"""

import sys
from typing import Optional

from boostgauge.app import BoostGaugeApp
from boostgauge.config import ConfigError, load_effective_config


def main(args: Optional[list[str]] = None) -> int:
    """Bootstrap BoostGauge application from CLI arguments."""
    try:
        config, config_path = load_effective_config(args)
    except ConfigError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    app = BoostGaugeApp(config, config_path)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())