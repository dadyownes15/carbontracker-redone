import logging
import queue
from dataclasses import dataclass, field, fields
from threading import Event, Thread
from typing import Any, Sequence

from carbontracker.config.config import LogLevel
from carbontracker.core.aggregator import AggregatorThread
from carbontracker.core.events import TrackerEvent
from carbontracker.core.profiling import SpanPowerProfiler
from carbontracker.core.types import Component, IntensityMethod, Location
from carbontracker.observers.base import ObserverThread
from carbontracker.observers.providers.manual import ManualObserverThread
from carbontracker.observers.providers.subprocess import SubprocessObserverThread
from carbontracker.providers.carbon_intensity.factory import create_intensity_thread
from carbontracker.providers.carbon_intensity_forecast.factory import (
    create_intensity_forecast_thread,
)
from carbontracker.providers.data_provider_thread import DataProviderThread
from carbontracker.providers.power.factory import create_power_thread
from carbontracker.reporters.file_logger import FileWriterThread
from carbontracker.reporters.logging_handler import EventQueueLogHandler
from carbontracker.reporters.terminal import TerminalOutputThread


def _normalize_provider_name(value: str) -> str:
    normalized = value.strip().replace("-", "_")
    if normalized.lower() in {"electricitymaps", "electricity_maps"}:
        return "electricity_maps"
    return normalized


def _coerce_log_level(value: LogLevel | str) -> LogLevel:
    if isinstance(value, LogLevel):
        return value
    try:
        return LogLevel(str(value).strip().lower())
    except ValueError as exc:
        raise ValueError(f"Invalid log level: {value}") from exc


def _coerce_intensity_method(value: IntensityMethod | str) -> IntensityMethod:
    if isinstance(value, IntensityMethod):
        return value
    normalized = str(value).strip().replace("-", "_").lower()
    if normalized == "electricitymaps":
        normalized = "electricity_maps"
    try:
        return IntensityMethod(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid intensity method: {value}") from exc


def _coerce_components(components: Sequence[Component | str] | None) -> list[Component]:
    if components is None:
        return [Component.CPU, Component.GPU, Component.RAM]
    if not components:
        raise ValueError("components must contain at least one component")

    resolved: list[Component] = []
    for component in components:
        if isinstance(component, Component):
            resolved.append(component)
            continue
        try:
            resolved.append(Component(str(component).strip().lower()))
        except ValueError as exc:
            raise ValueError(f"Invalid component: {component}") from exc
    return resolved


def _positive_number(name: str, value: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be greater than zero")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be greater than zero") from exc
    if numeric <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return numeric


@dataclass(frozen=True)
class RuntimeOptions:
    run_name: str = "carbontracker"
    log_dir: str = "carbontracker_logs/"
    ignore_errors: bool = True
    log_level: LogLevel | str = LogLevel.WARNING
    session_stat_interval_s: float = 1.0
    components: Sequence[Component | str] | None = None
    pue: float = 1.1
    power_sampling_interval: float = 15.0
    devices_by_pids: list[str] = field(default_factory=list)
    intensity_method: IntensityMethod | str = IntensityMethod.AUTO
    intensity_sampling_interval: float = 900.0
    location: Location | str | None = None
    static_carbon_intensity_g_per_kwh: float | None = None
    api_keys: dict[str, str] | None = None
    forecast_provider_name: str | None = None
    auto_detect_location: bool = True

    def __post_init__(self) -> None:
        run_name = str(self.run_name).strip()
        if not run_name:
            raise ValueError("run_name must be a non-empty string")
        object.__setattr__(self, "run_name", run_name)

        log_dir = str(self.log_dir).strip()
        if not log_dir:
            raise ValueError("log_dir must be a non-empty string")
        object.__setattr__(self, "log_dir", log_dir)

        object.__setattr__(self, "log_level", _coerce_log_level(self.log_level))
        object.__setattr__(self, "components", _coerce_components(self.components))
        object.__setattr__(
            self,
            "session_stat_interval_s",
            _positive_number("session_stat_interval_s", self.session_stat_interval_s),
        )
        object.__setattr__(self, "pue", _positive_number("pue", self.pue))
        object.__setattr__(
            self,
            "power_sampling_interval",
            _positive_number("power_sampling_interval", self.power_sampling_interval),
        )
        object.__setattr__(
            self,
            "intensity_sampling_interval",
            _positive_number(
                "intensity_sampling_interval", self.intensity_sampling_interval
            ),
        )
        object.__setattr__(
            self, "intensity_method", _coerce_intensity_method(self.intensity_method)
        )

        if self.static_carbon_intensity_g_per_kwh is not None:
            object.__setattr__(
                self,
                "static_carbon_intensity_g_per_kwh",
                _positive_number(
                    "static_carbon_intensity_g_per_kwh",
                    self.static_carbon_intensity_g_per_kwh,
                ),
            )

        if self.api_keys is None:
            api_keys: dict[str, str] = {}
        elif isinstance(self.api_keys, dict):
            api_keys = {
                _normalize_provider_name(str(key)): str(value)
                for key, value in self.api_keys.items()
            }
        else:
            raise ValueError("api_keys must be a dict when provided")
        object.__setattr__(self, "api_keys", api_keys)

        if self.forecast_provider_name is not None:
            object.__setattr__(
                self,
                "forecast_provider_name",
                _normalize_provider_name(self.forecast_provider_name),
            )

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "RuntimeOptions":
        option_fields = {field_.name for field_ in fields(cls)}
        return cls(
            **{key: value for key, value in values.items() if key in option_fields}
        )


class ManualRuntimeControls:
    def __init__(self, observer: ManualObserverThread) -> None:
        self._observer = observer
        self._active = False
        self._finished = False

    def epoch_start(self) -> None:
        if self._finished:
            raise RuntimeError("Cannot start an epoch after finish()")
        if self._active:
            raise RuntimeError("Cannot start a new epoch while another epoch is active")
        self._observer.manual_start()
        self._active = True

    def epoch_end(self) -> None:
        if self._finished:
            raise RuntimeError("Cannot end an epoch after finish()")
        if not self._active:
            raise RuntimeError("epoch_end() called before epoch_start()")
        self._observer.manual_end()
        self._active = False

    def mark_finished(self) -> None:
        self._finished = True


@dataclass
class RuntimeBundle:
    options: RuntimeOptions
    observer_thread: ObserverThread
    provider_threads: list[DataProviderThread[Any]]
    aggregator_thread: AggregatorThread
    reporter_threads: list[Thread]
    aggregation_queue: queue.Queue[TrackerEvent]
    terminal_queue: queue.Queue[TrackerEvent]
    logger_queue: queue.Queue[TrackerEvent]
    event_sink: list[queue.Queue[TrackerEvent]]
    manual_controls: ManualRuntimeControls | None = None

    @property
    def threads(self) -> list[Thread]:
        return [
            self.observer_thread,
            *self.provider_threads,
            self.aggregator_thread,
            *self.reporter_threads,
        ]


def _setup_logging(
    options: RuntimeOptions, event_sink: list[queue.Queue[TrackerEvent]]
) -> None:
    logger = logging.getLogger("carbontracker")
    logger.setLevel(options.log_level.value.upper())
    logger.propagate = False
    logger.handlers.clear()

    queue_handler = EventQueueLogHandler(event_sink)
    queue_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(queue_handler)


def _build_shared_runtime(
    options: RuntimeOptions,
    observer_thread: ObserverThread,
    provider_threads: list[DataProviderThread[Any]],
    aggregation_queue: queue.Queue[TrackerEvent],
    terminal_queue: queue.Queue[TrackerEvent],
    logger_queue: queue.Queue[TrackerEvent],
    event_sink: list[queue.Queue[TrackerEvent]],
    manual_controls: ManualRuntimeControls | None = None,
) -> RuntimeBundle:
    profiler = SpanPowerProfiler()
    aggregator_thread = AggregatorThread(
        session_stats_interval_s=options.session_stat_interval_s,
        aggregation_queue=aggregation_queue,
        event_sink=event_sink,
        profiler=profiler,
    )
    reporter_threads: list[Thread] = [
        TerminalOutputThread(log_level=options.log_level, event_queue=terminal_queue),
        FileWriterThread(
            log_dir=options.log_dir,
            run_name=options.run_name,
            event_queue=logger_queue,
        ),
    ]

    return RuntimeBundle(
        options=options,
        observer_thread=observer_thread,
        provider_threads=provider_threads,
        aggregator_thread=aggregator_thread,
        reporter_threads=reporter_threads,
        aggregation_queue=aggregation_queue,
        terminal_queue=terminal_queue,
        logger_queue=logger_queue,
        event_sink=event_sink,
        manual_controls=manual_controls,
    )


def _build_providers(
    options: RuntimeOptions,
    aggregation_queue: queue.Queue[TrackerEvent],
) -> tuple[list[DataProviderThread[Any]], list[Event]]:
    provider_threads: list[DataProviderThread[Any]] = []
    provider_trigger_events: list[Event] = []

    power_trigger = Event()
    provider_trigger_events.append(power_trigger)
    provider_threads.append(
        create_power_thread(
            config=options,
            aggregation_queue=aggregation_queue,
            notify_event=power_trigger,
        )
    )

    intensity_trigger = Event()
    provider_trigger_events.append(intensity_trigger)
    intensity_thread, intensity_resolution = create_intensity_thread(
        config=options,
        aggregation_queue=aggregation_queue,
        notify_event=intensity_trigger,
    )
    provider_threads.append(intensity_thread)

    forecast_provider_name = options.forecast_provider_name
    if forecast_provider_name is None:
        forecast_provider_name = (
            "electricity_maps"
            if intensity_resolution.provider_name == "electricity_maps"
            else "static"
        )

    forecast_api_key = (
        options.api_keys.get(forecast_provider_name) if forecast_provider_name else None
    )
    provider_threads.append(
        create_intensity_forecast_thread(
            location=intensity_resolution.location,
            aggregation_queue=aggregation_queue,
            current_intensity=intensity_resolution.static_intensity,
            provider_name=forecast_provider_name,
            api_key=forecast_api_key,
            forecast_length_hours=24,
            forecast_interval_hours=1,
            sample_interval=3600,
        )
    )

    return provider_threads, provider_trigger_events


def _runtime_parts(
    options: RuntimeOptions,
) -> tuple[
    queue.Queue[TrackerEvent],
    queue.Queue[TrackerEvent],
    queue.Queue[TrackerEvent],
    list[queue.Queue[TrackerEvent]],
    list[DataProviderThread[Any]],
    list[Event],
]:
    aggregation_queue: queue.Queue[TrackerEvent] = queue.Queue()
    terminal_queue: queue.Queue[TrackerEvent] = queue.Queue()
    logger_queue: queue.Queue[TrackerEvent] = queue.Queue()
    event_sink = [terminal_queue, logger_queue]

    _setup_logging(options, event_sink)
    provider_threads, provider_trigger_events = _build_providers(
        options, aggregation_queue
    )

    return (
        aggregation_queue,
        terminal_queue,
        logger_queue,
        event_sink,
        provider_threads,
        provider_trigger_events,
    )


def build_manual_runtime(options: RuntimeOptions) -> RuntimeBundle:
    (
        aggregation_queue,
        terminal_queue,
        logger_queue,
        event_sink,
        provider_threads,
        provider_trigger_events,
    ) = _runtime_parts(options)

    observer_thread = ManualObserverThread(
        aggregation_queue=aggregation_queue,
        event_sink=event_sink,
        notify_events=provider_trigger_events,
    )
    manual_controls = ManualRuntimeControls(observer_thread)

    return _build_shared_runtime(
        options=options,
        observer_thread=observer_thread,
        provider_threads=provider_threads,
        aggregation_queue=aggregation_queue,
        terminal_queue=terminal_queue,
        logger_queue=logger_queue,
        event_sink=event_sink,
        manual_controls=manual_controls,
    )


def build_subprocess_runtime(
    command: Sequence[str], options: RuntimeOptions
) -> RuntimeBundle:
    resolved_command = [str(part) for part in command]
    if not resolved_command or not any(part.strip() for part in resolved_command):
        raise ValueError("CLI command must be non-empty")

    (
        aggregation_queue,
        terminal_queue,
        logger_queue,
        event_sink,
        provider_threads,
        provider_trigger_events,
    ) = _runtime_parts(options)

    observer_thread = SubprocessObserverThread(
        command=resolved_command,
        aggregation_queue=aggregation_queue,
        event_sink=event_sink,
        notify_events=provider_trigger_events,
    )

    return _build_shared_runtime(
        options=options,
        observer_thread=observer_thread,
        provider_threads=provider_threads,
        aggregation_queue=aggregation_queue,
        terminal_queue=terminal_queue,
        logger_queue=logger_queue,
        event_sink=event_sink,
    )
