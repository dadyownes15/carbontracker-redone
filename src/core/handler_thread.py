import queue
from threading import Event, Thread
from time import time
from typing import Tuple
from typing_extensions import List, Dict, Any

from src.core.config import SessionConfig
from src.core.events import EventStart, EventStats, EventStop, TrackerEvent
from src.core.markers import Marker
from datetime import datetime

from src.data_provider.data_provider import MeasurementData
from src.data_provider.power.power_provider import PowerMeasurementData
from src.data_provider.carbon_intensity.intensity_provider import IntensityMeasurementData
from src.data_provider.factory import ProviderThread

class HandlerThread(Thread):
    def __init__(
        self,
        session_config: SessionConfig,
        provider_threads: List[ProviderThread],
        marker_queue: "queue.Queue[Marker]",
        event_sink: "List[queue.Queue[TrackerEvent]]",
        power_measurements: List[PowerMeasurementData],
        intensity_measurements: List[IntensityMeasurementData]
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
        self._power_measurements = power_measurements
        self._intensity_measurements = intensity_measurements
        self._measurements: List[MeasurementData] = []
        
        # Track emitted events
        self._last_power_idx = 0
        self._last_intensity_idx = 0
        
        # _poll_timeout is the maximum amount of time between provider fetches 
        # For accurate power calculations, it is essentially _poll_timeout is low, as point measurements on wattage usage usualy has high variance
        # It is expected that the providers can handle request efficiently, for example intensity measurement rarely changes within 15 minutes granularity, thus providers should have some caching logic.
        self._poll_timeout = 1.0 

    def run(self):
        while not self._stop_event.is_set():
            try:
                marker = self.marker_queue.get(timeout=self._poll_timeout)
                self._process_marker(marker)
                self.marker_queue.task_done()
                
            except queue.Empty:
                # Triggered when markerque has been empty for $_poll_timeout secounds
                self._run_periodic_tasks()

    def _process_marker(self, marker: Marker):
        if marker.span_id in self._active_spans:
            self._handle_marker_end(marker)
        else:
            self._handle_marker_start(marker)
            
    def _handle_marker_start(self, marker: Marker):
        """Snapshot the current state of the world when a marker begins."""
        self._active_spans[marker.span_id] = marker.timestamp
        event = EventStart(
           started_at=marker.timestamp,
           span_id=marker.span_id,
        ) 
        self._emit_event(event)
        
        # Get relevant measurements
        self._trigger_provider_measurements()
        self._flush_measurements()

    def _handle_marker_end(self, end_marker: Marker):
        if end_marker.span_id not in self._active_spans:
            raise ValueError("Marked end, without active span id found")

        eventStop = EventStop(
            ended_at=end_marker.timestamp,
            span_id=end_marker.span_id
        )
        self._emit_event(eventStop)

        self._trigger_provider_measurements()
        self._flush_measurements()

        eventStats = self._calc_event_stats(end_marker)
        self._emit_event(eventStats)
        self._clean_up(end_marker)

    def _trigger_provider_measurements(self) -> None:
        """
        Triggers an immediate fetch across all provider threads to snapshot the world
        and blocks until they finish.
        """
        events = [provider.trigger_fetch() for provider in self.provider_threads]
        for e in events:
            e.wait()

    def _run_periodic_tasks(self):
        """Logic executed every X seconds when no markers are arriving."""
        self._trigger_provider_measurements()

    def _flush_measurements(self):
        """Sweep the lists and stream new MeasurementEvents to the sinks."""
        from src.core.events import MeasurementEvent
        while self._last_power_idx < len(self._power_measurements):
            m = self._power_measurements[self._last_power_idx]
            self._emit_event(MeasurementEvent(provider_name="power", timestamp=m.timestamp, data=m))
            self._last_power_idx += 1
            
        while self._last_intensity_idx < len(self._intensity_measurements):
            m = self._intensity_measurements[self._last_intensity_idx]
            self._emit_event(MeasurementEvent(provider_name="intensity", timestamp=m.timestamp, data=m))
            self._last_intensity_idx += 1

    def _calc_event_stats(self,end_marker: Marker) -> EventStats:
        span_start: datetime = self._active_spans[end_marker.span_id]

        relevant_power = [
            m for m in self._power_measurements 
            if span_start <= m.timestamp <= end_marker.timestamp
        ]
        
        avg_watt = 0.0
        total_power_usage = 0.0
        max_watt = 0.0
        min_watt = 0.0
        
        if relevant_power:
            watts = []
            for p in relevant_power:
                watts.append(p.wattage)
            if watts:
                avg_watt = sum(watts) / len(watts)
                max_watt = max(watts)
                min_watt = min(watts)
                
            duration_hours = (end_marker.timestamp - span_start).total_seconds() / 3600.0
            total_power_usage = avg_watt * duration_hours

        relevant_intensity = [
            m for m in self._intensity_measurements 
            if span_start <= m.timestamp <= end_marker.timestamp
        ]
        
        avg_intensity = 0.0
        total_emissions = 0.0
        intensities = []
        if relevant_intensity:
            intensities = [m.intensity for m in relevant_intensity]
            if intensities:
                avg_intensity = sum(intensities) / len(intensities)
                total_emissions = total_power_usage * avg_intensity

        stats = {
            "total_power_usage": total_power_usage,
            "total_emissions": total_emissions,
            "average_intensity": avg_intensity,
            "max_intensity": max(intensities) if intensities else 0,
            "min_intensity": min(intensities) if intensities else 0,
            "avg_watt": avg_watt,
            "max_watt": max_watt,
            "min_watt": min_watt,
            "power_usage_pr_device": {}
        }

        event = EventStats(
            span_id=end_marker.span_id,
            started_at=span_start,
            ended_at=end_marker.timestamp,
            data=stats,
        )

        return event 
        
    def _clean_up(self, end_marker: Marker): 
        """
        Removes any measurements that are older than the oldest active span to minimize memory usage.
        """
        del self._active_spans[end_marker.span_id]
        
        if not self._active_spans:
            # If no active spans, clear everything up to the current indices
            self._power_measurements = self._power_measurements[self._last_power_idx:]
            self._last_power_idx = 0
            
            self._intensity_measurements = self._intensity_measurements[self._last_intensity_idx:]
            self._last_intensity_idx = 0
        else:
            oldest_span_start = min(self._active_spans.values())
            
            # Count how many power measurements are older than the oldest span
            p_idx = 0
            while p_idx < len(self._power_measurements) and self._power_measurements[p_idx].timestamp < oldest_span_start:
                p_idx += 1
                
            if p_idx > 0 and p_idx <= self._last_power_idx:
                self._power_measurements = self._power_measurements[p_idx:]
                self._last_power_idx -= p_idx

            # Same for intensity
            i_idx = 0
            while i_idx < len(self._intensity_measurements) and self._intensity_measurements[i_idx].timestamp < oldest_span_start:
                i_idx += 1
                
            if i_idx > 0 and i_idx <= self._last_intensity_idx:
                self._intensity_measurements = self._intensity_measurements[i_idx:]
                self._last_intensity_idx -= i_idx

    def _emit_event(self, event: TrackerEvent):
        """Broadcasts an event to all configured sinks."""
        for sink in self.event_sink:
            sink.put(event)

    def stop(self):
        self._stop_event.set()