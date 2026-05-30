import os
import queue
import subprocess
import sys
import uuid
from datetime import datetime
from threading import Event, Thread
from typing import List, Optional

from carbontracker.core.events import (
    ProcessExitedEvent,
    ProcessOutputEvent,
    ProcessStartedEvent,
    TrackerEvent,
)
from carbontracker.core.markers import Marker
from carbontracker.observers.base import ObserverThread

class SubprocessObserverThread(ObserverThread):
    def __init__(
        self,
        command: List[str],
        aggregation_queue: "queue.Queue[TrackerEvent]",
        event_sink: "List[queue.Queue[TrackerEvent]]",
        notify_events: List[Event],
        trace_id: str | None = None,
        capture_output_events: bool = False,
    ) -> None:
        super().__init__(
            aggregation_queue=aggregation_queue,
            event_sink=event_sink,
            notify_events=notify_events,
            name="subprocess"
        )
        self.command = command
        self._span_stack: List[str] = []
        self._trace_id = trace_id if trace_id is not None else str(uuid.uuid4())
        self.capture_output_events = capture_output_events

    def _make_marker(self, span_id: str, parent_span_id: Optional[str]) -> Marker:
        return Marker(
            marker_id=str(uuid.uuid4()),
            trace_id=self._trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            timestamp=datetime.now()
        )

    def _emit_event(self, event: TrackerEvent) -> None:
        for sink in self.event_sink:
            sink.put(event)

    def _handle_stdout_line(self, line: str) -> None:
        if line.startswith("carbontracker:"):
            self._handle_marker(line.strip())
            return
        if self.capture_output_events:
            self._emit_event(
                ProcessOutputEvent(
                    timestamp=datetime.now(),
                    stream="stdout",
                    line=line.rstrip("\n"),
                    trace_id=self._trace_id,
                )
            )
        else:
            sys.stdout.write(line)
            sys.stdout.flush()

    def _handle_stderr_line(self, line: str) -> None:
        if self.capture_output_events:
            self._emit_event(
                ProcessOutputEvent(
                    timestamp=datetime.now(),
                    stream="stderr",
                    line=line.rstrip("\n"),
                    trace_id=self._trace_id,
                )
            )
        else:
            sys.stderr.write(line)
            sys.stderr.flush()

    def run(self) -> None:
        if not self.command:
            return

        # Emit root span start
        root_span = "process"
        self._span_stack.append(root_span)
        self._emit_start(self._make_marker(root_span, parent_span_id=None))

        env = os.environ.copy()
        # Ensure python processes are unbuffered so we get markers immediately
        env["PYTHONUNBUFFERED"] = "1"
        env["CARBONTRACKER_TRACE_ID"] = self._trace_id
        
        proc = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if self.capture_output_events else None,
            env=env,
            text=True,
            bufsize=1,  # line-buffered
        )
        self._emit_event(
            ProcessStartedEvent(
                timestamp=datetime.now(),
                command=tuple(self.command),
                pid=proc.pid,
                trace_id=self._trace_id,
            )
        )

        stdout_thread = None
        stderr_thread = None
        interrupted = False

        if proc.stdout is not None:
            stdout_thread = Thread(
                target=self._drain_stream,
                args=(proc.stdout, self._handle_stdout_line),
                daemon=True,
            )
            stdout_thread.start()

        if proc.stderr is not None:
            stderr_thread = Thread(
                target=self._drain_stream,
                args=(proc.stderr, self._handle_stderr_line),
                daemon=True,
            )
            stderr_thread.start()

        try:
            while proc.poll() is None:
                if self._stop_event.wait(timeout=0.1):
                    interrupted = True
                    proc.terminate()
                    break
            proc.wait()
        except KeyboardInterrupt:
            interrupted = True
            proc.terminate()
            proc.wait()
            raise
        finally:
            if stdout_thread is not None:
                stdout_thread.join()
            if stderr_thread is not None:
                stderr_thread.join()
            self._emit_event(
                ProcessExitedEvent(
                    timestamp=datetime.now(),
                    return_code=proc.returncode,
                    interrupted=interrupted,
                    trace_id=self._trace_id,
                )
            )

        # Close any unclosed spans (in reverse order)
        while self._span_stack:
            span = self._span_stack.pop()
            parent = self._span_stack[-1] if self._span_stack else None
            self._emit_stop(self._make_marker(span, parent_span_id=parent))

    def _drain_stream(self, stream, line_handler) -> None:
        try:
            for line in stream:
                line_handler(line)
        finally:
            stream.close()

    def _handle_marker(self, line: str) -> None:
        parts = line.split(":")
        if len(parts) < 3:
            return
            
        # Expected format: carbontracker:<unit_name>:start or carbontracker:<unit_name>:end
        name = parts[1]
        action = parts[2].split("?")[0] # Strip off any query params for now

        if action == "start":
            parent = self._span_stack[-1] if self._span_stack else None
            self._span_stack.append(name)
            self._emit_start(self._make_marker(name, parent_span_id=parent))
        elif action == "end":
            if name in self._span_stack:
                # Close all spans down to this one
                idx = self._span_stack.index(name)
                spans_to_close = self._span_stack[idx:]
                for span in reversed(spans_to_close):
                    self._span_stack.remove(span)
                    parent = self._span_stack[-1] if self._span_stack else None
                    self._emit_stop(self._make_marker(span, parent_span_id=parent))
