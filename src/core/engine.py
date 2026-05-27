import logging
import threading
from queue import Queue
from threading import Event, Thread
from typing import Union

from src.core.aggregator import AggregatorThread
from src.config.config import SessionConfig, SessionMode
from src.core.events import FinishedSession, TrackerEvent
from src.core.exceptions import WrongModeError
from src.core.execution_guard import GuardVerdict
from src.reporters.file_logger import FileWriterThread
from src.reporters.logging_handler import EventQueueLogHandler
from src.reporters.terminal import TerminalOutputThread
from src.providers.data_provider import MeasurementData
from src.providers.base import DataProviderThread
from src.providers.factory import provider_factory
from src.providers.power.power_provider import PowerMeasurementData
from src.observers.base import ObserverThread
from src.observers.factory import observer_factory


class CarbonTrackerEngine:

    """
    CarbonTrackerEngine: Used for managing the various threads during the tracking session
    """

    def __init__(
        self,
        session_config: SessionConfig,
    ):

        self.session_config: SessionConfig = session_config

        #Unimplemented modes:
        missing_modes: list[SessionMode] = [SessionMode.PYTHON_DECORATOR, SessionMode.SLURM,SessionMode.SUBPROCESS]
        if self.session_config.mode in missing_modes:
            raise ValueError(f"{self.session_config.mode} is not implemented")

        # Queues
        self.aggregation_queue: Queue[TrackerEvent] = Queue()
        self.terminal_queue: Queue[TrackerEvent] = Queue()
        self.logger_queue: Queue[TrackerEvent] = Queue()
        self.event_sink: list[Queue[TrackerEvent]] = [
            self.terminal_queue,
            self.logger_queue,
        ]

        self._setup_logging()

        # Build provider threads with shared trigger events
        self.provider_threads: list[
            DataProviderThread[MeasurementData | PowerMeasurementData]
        ] = []
        self.provider_trigger_events: list[Event] = []

        for p_config in self.session_config.provider_configs:
            trigger: Event = Event()
            self.provider_trigger_events.append(trigger)
            self.provider_threads.append(
                provider_factory(
                    aggregation_queue=self.aggregation_queue,
                    config=p_config,
                    notify_event=trigger,
                )
            )

        self.observer_thread: ObserverThread = observer_factory(
            config=self.session_config.observer_config,
            mode=self.session_config.mode,
            aggregation_queue=self.aggregation_queue,
            event_sink=self.event_sink,
            notify_events=self.provider_trigger_events,
        )

        self._guard_triggered: Event = Event()
        self._guard_verdict: GuardVerdict | None = None

        def _default_guard_callback(verdict: GuardVerdict):
            # TODO (dadyownes15):
            # Add proper gaurd callbacks that match the config
            self._guard_verdict = verdict
            self._guard_triggered.set()
            self.logger.warning("Budget has been violated: ", verdict.reason)

        self.aggregator_thread: AggregatorThread = AggregatorThread(
            prediction_config=self.session_config.prediction_config,
            budget_policy=self.session_config.budget_policy,
            stats_emit_interval_s=self.session_config.session_stat_interval_s,
            mode=self.session_config.mode,
            aggregation_queue=self.aggregation_queue,
            event_sink=self.event_sink,
            guard_callback=_default_guard_callback
            if self.session_config.mode.is_python
            else None,
        )

        self.terminal_thread: TerminalOutputThread = TerminalOutputThread(
            log_level=self.session_config.log_level, event_queue=self.terminal_queue
        )
        self.file_writer_thread: FileWriterThread = FileWriterThread(
            log_dir=self.session_config.log_dir,
            run_name=self.session_config.run_name,
            event_queue=self.logger_queue,
        )

        # Order is important here for proper closedown
        self.threads: list[Thread] = [
            self.observer_thread,
            *self.provider_threads,
            self.aggregator_thread,
            self.terminal_thread,
            self.file_writer_thread,
        ]

        for thread in self.threads:
            thread.start()

        self.logger.debug("Active threads list:")
        for thread in threading.enumerate():
            self.logger.debug(
                f" - Name: {thread.name}, ID: {thread.native_id}, Daemon: {thread.daemon}"
            )

    def _setup_logging(self):
        self.logger = logging.getLogger("carbontracker")
        self.logger.setLevel(self.session_config.log_level.value.upper())
        self.logger.propagate = False
        self.logger.handlers.clear()

        queue_handler = EventQueueLogHandler(self.event_sink)
        formatter = logging.Formatter("%(message)s")
        queue_handler.setFormatter(formatter)
        self.logger.addHandler(queue_handler)

    def epoch_start(self):
        if self.session_config.mode != SessionMode.PYTHON_API:
            raise WrongModeError(
                "epoch_start() is only available in python-manual mode"
            )
        self.observer_thread.manual_start()

    def epoch_end(self):
        if self.session_config.mode != SessionMode.PYTHON_API:
            raise WrongModeError(
                "epoch_start() is only available in python-manual mode"
            )  # using proper exception later
        self.observer_thread.manual_end()

    def finish(self) -> FinishedSession:
        final_stats = None

        for thread in self.threads:
            result = thread.stop()
            if isinstance(thread, AggregatorThread):
                final_stats: FinishedSession = result
            thread.join()

        for thread in threading.enumerate():
            self.logger.debug(
                "f - Name: {thread.name}, ID: {thread.native_id}, Daemon: {thread.daemon}"
            )

        return final_stats
