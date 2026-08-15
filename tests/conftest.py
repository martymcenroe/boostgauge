"""Pytest configuration.

Issue #1: Feature: core gauge renderer
"""

def pytest_addoption(parser):
    parser.addoption("--generate-baselines", action="store_true", help="Generate new visual baselines")