import os
import queue
import subprocess
import sys
import uuid
from datetime import datetime
from threading import Event
from typing import List, Optional

from carbontracker.core.markers import Marker
from carbontracker.core.events import TrackerEvent
from carbontracker.observers.base import ObserverThread

class SubprocessObserverThread(ObserverThread):
    def __init__(
        self,
        command: List[str],
        aggregation_queue: "queue.Queue[TrackerEvent]",
        event_sink: "List[queue.Queue[TrackerEvent]]",
        notify_events: List[Event]
    ) -> None:
        super().__init__(
            aggregation_queue=aggregation_queue,
            event_sink=event_sink,
            notify_events=notify_events,
            name="subprocess"
        )
        self.command = command
        self._span_stack: List[str] = []
        self._trace_id = str(uuid.uuid4())

    def _make_marker(self, span_id: str, parent_span_id: Optional[str]) -> Marker:
        return Marker(
            marker_id=str(uuid.uuid4()),
            trace_id=self._trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            timestamp=datetime.now()
        )

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
            stderr=None,  # stderr goes straight to terminal
            env=env,
            text=True,
            bufsize=1,  # line-buffered
        )

        if proc.stdout:
            for line in proc.stdout:
                if line.startswith("carbontracker:"):
                    self._handle_marker(line.strip())
                else:
                    sys.stdout.write(line)
                    sys.stdout.flush()

        proc.wait()

        # Close any unclosed spans (in reverse order)
        while self._span_stack:
            span = self._span_stack.pop()
            parent = self._span_stack[-1] if self._span_stack else None
            self._emit_stop(self._make_marker(span, parent_span_id=parent))

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
