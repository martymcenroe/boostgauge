"""Application CLI entry point integrating argparse CLI options, configuration loading, and application initialization.

Issue #7: Feature: Configuration File and CLI Arguments
"""

from __future__ import annotations

from pathlib import Path
import sys

from boostgauge.config import (
    get_default_config_path,
    load_config,
    merge_config_and_args,
    parse_cli_args,
    reset_config_to_defaults,
    validate_config,
)


def main(sys_args: list[str] | None = None) -> int:
    """Main CLI entry point for boostgauge."""
    try:
        cli_args = parse_cli_args(sys_args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    config_path = Path(cli_args.config) if cli_args.config else get_default_config_path()

    if cli_args.reset_config:
        reset_config_to_defaults(config_path)
        print(f"Reset configuration to defaults at {config_path}")
        return 0

    try:
        config = load_config(config_path)
    except ValueError as err:
        print(f"Error loading configuration: {err}", file=sys.stderr)
        return 1

    config = merge_config_and_args(config, cli_args)
    validation_errors = validate_config(config)

    if validation_errors:
        print("Configuration validation errors:", file=sys.stderr)
        for error in validation_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())