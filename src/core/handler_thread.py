import queue
from threading import Event, Thread
from time import time
from turtle import st
from typing import Tuple
from typing_extensions import List, Dict, Any

from src.core.config import SessionConfig
from src.core.events import EventStart, EventStats, EventStop, TrackerEvent
from src.core.markers import Marker
from datetime import datetime

from src.data_provider.data_provider import MeasurementData

class HandlerThread(Thread):
    def __init__(
        self,
        session_config: SessionConfig,
        provider_threads: List[Thread],
        marker_queue: "queue.Queue[Marker]",
        event_sink: "List[queue.Queue[TrackerEvent]]"
    ) -> None:
        super().__init__()
        self.session_config = session_config
        self.provider_threads = provider_threads
        self.marker_queue = marker_queue
        self.event_sink = event_sink
        
        self._stop_event = Event()

        # State Management for Aggregations
        
        self._aggregate_stats = {
            "total_power": 0.0,
            "total_emissions": 0.0
        }

        self._active_spans: Dict[str,datetime] = {} 
        self._measurements: List[MeasurementData] = []
        
        # Polling frequency for time-based logic (seconds)
        self._poll_timeout = 1.0 

    def run(self):
        while not self._stop_event.is_set():
            try:
                marker = self.marker_queue.get(timeout=self._poll_timeout)
                self._process_marker(marker)
                self.marker_queue.task_done()
                
            except queue.Empty:
                self._run_periodic_tasks()

    def _process_marker(self, marker: Marker):
        if marker.span_id in self._active_spans:
            self._handle_marker_end(marker)
        else:
            self._handle_marker_start(marker)
            
    def _handle_marker_start(self, marker: Marker):
        """Snapshot the current state of the world when a marker begins."""
        # Get relevant measurements
        self._get_provider_measurements()
        self._active_spans[marker.span_id] = marker.timestamp
        event = EventStart(
           started_at=marker.timestamp,
           span_id=marker.span_id,
        ) 
        self._emit_event(event)
        

    def _handle_marker_end(self, end_marker: Marker):
        if end_marker.span_id not in self._active_spans:
            raise ValueError("Marked end, without active span id found")
            return  # Handle edge case where end arrives without a start

        self._get_provider_measurements()
        eventStop = EventStop(
            ended_at=end_marker.timestamp,
            span_id=end_marker.span_id
        )
        self._emit_event(eventStop)
        eventStats = self._calc_event_stats(end_marker)
        self._emit_event(eventStats)
        self._clean_up(end_marker)

    def _get_provider_measurements(self) -> Dict[str,Any]:
        """
        Gathers current data from providers. 
        Note: Providers should expose a thread-safe property or method (e.g., provider.latest_data).
        """
        total_power = 0.0
        total_emissions = 0.0

        # This seems unstable. we should use the provider register for handling this better
        for provider in self.provider_threads:
            # Assuming providers have a thread-safe method to get their latest reading
            if hasattr(provider, 'get_latest_reading'):
                reading = provider.get_latest_reading()
                total_power += reading.get("power", 0)
                total_emissions += reading.get("emissions", 0)
                
        return {"power": total_power, "emissions": total_emissions}

    def _run_periodic_tasks(self):
        """Logic executed every X seconds when no markers are arriving."""
        pass

    def _calc_event_stats(self,end_marker: Marker) -> EventStats:
        # pop span
        span_start: datetime = self._active_spans[end_marker.span_id]

        stats = {
            "total_power_usage": 0,
            "total_emissions": 0,
            "average_intensity": 0,
            "max_intensity": 0,
            "min_intensity": 0,
            "avg_watt": 0,
            "max_watt": 0,
            "min_watt": 0,
            "power_usage_pr_device": {
                "gpu:0": {},
                "gpu:1": {}
            }
        }

        event = EventStats(
            span_id=end_marker.span_id,
            started_at=span_start,
            ended_at=end_marker.timestamp,
            data=stats,
        )

        return event 
        
    def _clean_up(self,end_marker: Marker): 
        """
        Removes the span id

        Removes any measurements, that is uneeded for future to minimize memory usage for the caching of the measurements

        """
        pass


    def _emit_event(self, event: TrackerEvent):
        """Broadcasts an event to all configured sinks."""
        for sink in self.event_sink:
            sink.put(event)

    def stop(self):
        self._stop_event.set()