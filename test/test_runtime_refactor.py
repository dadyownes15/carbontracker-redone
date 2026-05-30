import queue
import sys

import pytest
from click.testing import CliRunner

from carbontracker.core.engine import CarbonTrackerEngine
from carbontracker.core.exceptions import WrongModeError
from carbontracker.core.runtime import RuntimeBundle, RuntimeOptions, build_subprocess_runtime
from carbontracker.core.stats import SessionFinalStats
from carbontracker.core.types import Component
from carbontracker.entrypoints.cli import cli as cli_module
from carbontracker.entrypoints.programmatic import manual as manual_module


class FakeThread:
    def __init__(self, name: str, stop_result=None) -> None:
        self.name = name
        self.native_id = None
        self.daemon = True
        self.stop_result = stop_result
        self.started = False
        self.stopped = False
        self.joined = 0

    def start(self) -> None:
        self.started = True

    def stop(self):
        self.stopped = True
        return self.stop_result

    def join(self) -> None:
        self.joined += 1


class FakeManualControls:
    def __init__(self) -> None:
        self.starts = 0
        self.ends = 0
        self.finished = False

    def epoch_start(self) -> None:
        self.starts += 1

    def epoch_end(self) -> None:
        self.ends += 1

    def mark_finished(self) -> None:
        self.finished = True


def make_fake_bundle(manual_controls=None):
    stats = SessionFinalStats(
        total_emissions_g=1.0,
        total_power_usage_kwh=2.0,
        duration_s=3.0,
        completed_spans_count=4,
    )
    aggregation_queue = queue.Queue()
    terminal_queue = queue.Queue()
    logger_queue = queue.Queue()
    observer = FakeThread("observer")
    provider = FakeThread("provider")
    aggregator = FakeThread("aggregator", stop_result=stats)
    reporter = FakeThread("reporter")
    bundle = RuntimeBundle(
        options=RuntimeOptions(run_name="test", auto_detect_location=False),
        observer_thread=observer,
        provider_threads=[provider],
        aggregator_thread=aggregator,
        reporter_threads=[reporter],
        aggregation_queue=aggregation_queue,
        terminal_queue=terminal_queue,
        logger_queue=logger_queue,
        event_sink=[terminal_queue, logger_queue],
        manual_controls=manual_controls,
    )
    return bundle, stats


def test_engine_starts_stops_joins_runtime_threads():
    bundle, expected_stats = make_fake_bundle()

    engine = CarbonTrackerEngine(bundle)
    assert all(thread.started for thread in bundle.threads)

    stats = engine.finish()

    assert stats == expected_stats
    assert all(thread.stopped for thread in bundle.threads)
    assert all(thread.joined == 1 for thread in bundle.threads)


def test_engine_manual_controls_fail_when_absent():
    bundle, _ = make_fake_bundle()
    engine = CarbonTrackerEngine(bundle)

    with pytest.raises(WrongModeError):
        engine.epoch_start()

    engine.finish()


def test_manual_constructor_rejects_invalid_args_before_build(monkeypatch):
    def fail_build(_options):
        raise AssertionError("runtime builder should not be called")

    monkeypatch.setattr(manual_module, "build_manual_runtime", fail_build)

    with pytest.raises(ValueError, match="pue"):
        manual_module.CarbonTracker(epochs=1, pue=0)

    with pytest.raises(NotImplementedError, match="max_energy_kwh"):
        manual_module.CarbonTracker(epochs=1, max_energy_kwh=1.0)


def test_manual_lifecycle_delegates_to_runtime_controls(monkeypatch):
    controls = FakeManualControls()
    bundle, expected_stats = make_fake_bundle(manual_controls=controls)
    captured = {}

    def fake_build(options):
        captured["options"] = options
        return bundle

    monkeypatch.setattr(manual_module, "build_manual_runtime", fake_build)

    tracker = manual_module.CarbonTracker(epochs=1, components=["cpu"])
    tracker.epoch_start()
    tracker.epoch_end()
    stats = tracker.finish()

    assert captured["options"].components == [Component.CPU]
    assert controls.starts == 1
    assert controls.ends == 1
    assert controls.finished is True
    assert stats == expected_stats


def test_subprocess_runtime_rejects_empty_command():
    options = RuntimeOptions(run_name="test", auto_detect_location=False)

    with pytest.raises(ValueError, match="command"):
        build_subprocess_runtime([], options)


def test_cli_hidden_run_builds_subprocess_runtime_and_finishes(monkeypatch, tmp_path):
    script = tmp_path / "tiny.py"
    script.write_text("print('ok')\n")
    bundle, _ = make_fake_bundle()
    captured = {}

    monkeypatch.setattr(cli_module, "resolve_overrides", lambda **kwargs: kwargs)

    def fake_build(command, options):
        captured["command"] = command
        captured["options"] = options
        return bundle

    monkeypatch.setattr(cli_module, "build_subprocess_runtime", fake_build)

    result = CliRunner().invoke(cli_module.main, [sys.executable, str(script)])

    assert result.exit_code == 0
    assert captured["command"] == [sys.executable, str(script)]
    assert isinstance(captured["options"], RuntimeOptions)
    assert bundle.observer_thread.joined == 2
    assert bundle.aggregator_thread.stopped is True
