from queue import Queue
from threading import Thread
import sys
import logging

from src.core.config import LogLevel
from src.core.events import MeasurementEvent, TrackerEvent, DiagnosticEvent, LogSeverity
from src.core.utils import SEVERITY_MAP


class TerminalOutputThread(Thread):
    def __init__(self, log_level: LogLevel, event_queue: Queue[TrackerEvent]):
        super().__init__()
        self.log_level: LogLevel = log_level
        self.event_queue: Queue[TrackerEvent] = event_queue
        self.name = "Terminal Output Thread"

        # Making it a daemon thread ensures it automatically shuts down
        # when your main application exits
        self.daemon = True

    def stop(self) -> None:
        self.event_queue.put(None)

    def run(self) -> None:
        """Continuously monitors the queue and prints incoming events based on verbosity."""
        while True:
            event = self.event_queue.get()

            # Close signal
            if event is None:
                self.event_queue.task_done()
                break

            if isinstance(event, DiagnosticEvent):
                event_level = SEVERITY_MAP.get(event.severity, logging.INFO)
                if event_level >= self.log_level:
                    if event.severity in [
                        LogSeverity.WARNING,
                        LogSeverity.ERROR,
                        LogSeverity.CRITICAL,
                    ]:
                        print(
                            f"[{event.severity.value}] {event.message}", file=sys.stderr
                        )
                    elif event.severity == LogSeverity.INFO:
                        print(f"[INFO] {event.message}")
                    elif event.severity == LogSeverity.DEBUG:
                        print(f"[DEBUG] {event.message}")
            else:
                # Print out other events only if verbosity allows
                if self.log_level <= logging.INFO:
                    print(f"[Carbontracker] Processing Event: {type(event).__name__}")

            # Tell the queue that processing for this item is complete
            self.event_queue.task_done()
