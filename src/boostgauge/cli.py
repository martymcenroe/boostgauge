"""CLI argument parser definition, option handling, and CLI-to-config override mapping logic.

Issue #7: Configuration File and CLI Arguments
"""

import argparse
from dataclasses import asdict
from typing import Optional, List
from boostgauge.config import GaugeConfig, validate_config


def build_cli_parser() -> argparse.ArgumentParser:
    """Construct and configure the argparse parser with all supported command line options."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer for monitoring AI agent resource pressure.",
    )
    parser.add_argument(
        "--theme",
        type=str,
        choices=["dark", "light"],
        help="UI color theme (dark or light)",
    )
    parser.add_argument(
        "--size",
        type=int,
        help="Gauge window size in pixels (100-2000)",
    )
    parser.add_argument(
        "--poll",
        type=int,
        help="System metric polling interval in seconds",
    )
    parser.add_argument(
        "--opacity",
        type=float,
        help="Window opacity (0.1 - 1.0)",
    )
    parser.add_argument(
        "--no-topmost",
        action="store_true",
        default=False,
        help="Disable always-on-top window behavior",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom JSON configuration file",
    )
    parser.add_argument(
        "--reset-config",
        action="store_true",
        default=False,
        help="Reset configuration file to default values on disk",
    )
    return parser


def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse raw command line argument strings into structured Namespace object."""
    parser = build_cli_parser()
    return parser.parse_args(args)


def merge_cli_overrides(config: GaugeConfig, parsed_args: argparse.Namespace) -> GaugeConfig:
    """Apply non-None CLI options onto existing GaugeConfig instance without altering disk state."""
    if parsed_args.theme is not None:
        config.theme = parsed_args.theme
    if parsed_args.size is not None:
        config.size = parsed_args.size
    if parsed_args.poll is not None:
        config.polling_interval_seconds = parsed_args.poll
    if parsed_args.opacity is not None:
        config.opacity = parsed_args.opacity
    if parsed_args.no_topmost:
        config.always_on_top = False

    validate_config(asdict(config))
    return config