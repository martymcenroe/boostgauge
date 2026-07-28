"""Application entry point executing CLI parsing, config loading, and runtime initialization.

Issue #7: Configuration File and CLI Arguments
"""

from typing import Optional, List
from pathlib import Path
from boostgauge.config import (
    GaugeConfig,
    get_default_config,
    get_default_config_path,
    load_config,
    save_config,
)
from boostgauge.cli import parse_cli_args, merge_cli_overrides


def main(args: Optional[List[str]] = None) -> GaugeConfig:
    """Run BoostGauge configuration initialization lifecycle and return active config."""
    parsed_args = parse_cli_args(args)
    config_path = Path(parsed_args.config) if parsed_args.config else get_default_config_path()

    if parsed_args.reset_config:
        config = get_default_config()
        save_config(config, config_path)
    else:
        config = load_config(config_path)

    merged_config = merge_cli_overrides(config, parsed_args)
    return merged_config


if __name__ == "__main__":
    main()