"""Contract tests for DataCollector interface compliance.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import time
import pytest
from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import get_collector


class TestDataCollectorContract:
    """Contract verification suite for DataCollector implementations."""

    @pytest.mark.parametrize("platform", ["win32", "linux"])
    def test_factory_returns_datacollector_subclass(self, platform: str) -> None:
        collector = get_collector(platform_name=platform)
        assert isinstance(collector, DataCollector)

    def test_collect_snapshot_returns_valid_system_snapshot(self) -> None:
        collector = get_collector()
        now = time.time()
        snapshot = collector.collect_snapshot(now)

        assert isinstance(snapshot, SystemSnapshot)
        assert snapshot.timestamp == pytest.approx(now, abs=1.0)
        assert snapshot.conpty_count >= 0
        assert snapshot.process_count >= 0
        assert 0.0 <= snapshot.memory_percent <= 100.0
        assert snapshot.handle_count >= 0
        assert snapshot.unleashed_sessions >= 0
        assert snapshot.driver in ("conpty", "memory", "process", "handle")
        assert 0.0 <= snapshot.composite_value <= 100.0

    def test_lifecycle_start_stop_is_running(self) -> None:
        collector = get_collector(config={"poll_interval": 0.1})
        assert not collector.is_running()

        collector.start()
        assert collector.is_running()

        time.sleep(0.3)
        snapshot = collector.get_latest_snapshot()
        assert snapshot is not None
        assert isinstance(snapshot, SystemSnapshot)

        collector.stop()
        assert not collector.is_running()