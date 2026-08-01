"""BoostGauge system monitor package.

Issue #7: Configuration File and CLI Arguments
"""

__version__ = "0.1.0"

from boostgauge.config import AppConfig, ConfigManager, WindowPosition, ThresholdsConfig, ThresholdPair

__all__ = [
    "__version__",
    "AppConfig",
    "ConfigManager",
    "WindowPosition",
    "ThresholdsConfig",
    "ThresholdPair",
]