"""Application runtime controller integrating configuration lifecycle.

Issue #7: Configuration File and CLI Arguments
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
    validate_config,
)


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

        return 0

    except ConfigError as exc:
        print(f"BoostGauge Configuration Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())