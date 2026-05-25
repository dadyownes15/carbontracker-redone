import queue
import logging
from threading import Thread, Event
from typing import Dict, List, Optional
from datetime import datetime

from src.core.config import SessionConfig
from src.core.events import TrackerEvent, EventStart, EventStop, MeasurementEvent, EventStats, SessionCurrentStatsEvent, DiagnosticEvent
from src.core.stats import EventStatsData, SessionStatsData
from src.data_provider.power.power_provider import PowerMeasurementData
from src.data_provider.carbon_intensity.intensity_provider import IntensityMeasurementData

logger = logging.getLogger("carbontracker.aggregator")

class AggregatorThread(Thread):
    def __init__(
        self,
        session_config: SessionConfig,
        aggregation_queue: "queue.Queue[TrackerEvent]",
        event_sink: "List[queue.Queue[TrackerEvent]]"
    ) -> None:
        super().__init__()
        self.session_config = session_config
        self.aggregation_queue = aggregation_queue
        self.event_sink = event_sink
        
        self._stop_event = Event()
        self.daemon = True
        self.name = "aggregator_thread"

        # Internal State
        self._active_spans: Dict[str, datetime] = {}
        self._power_measurements: List[PowerMeasurementData] = []
        self._intensity_measurements: List[IntensityMeasurementData] = []
        
        # Cumulative Stats
        self._cumulative_emissions_g: float = 0.0
        self._cumulative_power_kwh: float = 0.0
        
        self._completed_spans_count: int = 0
        
        # To store predictions
        self._predicted_total_power_kwh: Optional[float] = None
        self._predicted_total_emissions_g: Optional[float] = None
        self._forecast_intensity: Optional[float] = None

    def stop(self) -> None:
        self._stop_event.set()
        self.aggregation_queue.put(None) # type: ignore

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = self.aggregation_queue.get(timeout=1.0)
                if event is None:
                    continue # Sentinel value
                    
                if isinstance(event, EventStart):
                    self._handle_start(event)
                elif isinstance(event, EventStop):
                    self._handle_stop(event)
                elif isinstance(event, MeasurementEvent):
                    self._handle_measurement(event)
                    
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Aggregator encountered error processing event: {e}")

    def _handle_start(self, event: EventStart) -> None:
        self._active_spans[event.span_id] = event.started_at

    def _handle_measurement(self, event: MeasurementEvent) -> None:
        if isinstance(event.data, PowerMeasurementData):
            self._power_measurements.append(event.data)
        elif isinstance(event.data, IntensityMeasurementData):
            self._intensity_measurements.append(event.data)
            
        for sink in self.event_sink:
            sink.put(event)
            
        self._emit_session_stats()

    def _handle_stop(self, event: EventStop) -> None:
        span_id = event.span_id
        if span_id not in self._active_spans:
            return
            
        started_at = self._active_spans.pop(span_id)
        ended_at = event.ended_at
        
        # Slice measurements for this span
        span_power = [m for m in self._power_measurements if started_at <= m.timestamp <= ended_at]
        span_intensity = [m for m in self._intensity_measurements if started_at <= m.timestamp <= ended_at]
        
        # Compute event stats
        event_stats_data = self._compute_event_stats(span_power, span_intensity, started_at, ended_at)
        
        # Update cumulative
        self._cumulative_emissions_g += event_stats_data.emissions_g
        self._cumulative_power_kwh += event_stats_data.power_usage_kwh
        self._completed_spans_count += 1
        
        # Emit EventStats
        stats_event = EventStats(
            span_id=span_id,
            started_at=started_at,
            ended_at=ended_at,
            stats=event_stats_data
        )
        for sink in self.event_sink:
            sink.put(stats_event)
            
        # Compute prediction
        self._update_predictions()
        
        # Emit global session stats
        self._emit_session_stats()
        
        # Memory cleanup
        self._cleanup_old_measurements()
        
    def _compute_event_stats(self, power_m: List[PowerMeasurementData], intensity_m: List[IntensityMeasurementData], start: datetime, end: datetime) -> EventStatsData:
        duration_hours = (end - start).total_seconds() / 3600.0
        
        if not power_m:
            return EventStatsData(
                avg_watt=0.0, min_watt=0.0, max_watt=0.0,
                avg_intensity=0.0, min_intensity=0.0, max_intensity=0.0,
                power_usage_pr_device={}, emissions_g=0.0, power_usage_kwh=0.0,
                power_measurements_count=0, intensity_measurements_count=len(intensity_m)
            )
            
        watts = [sum(m.power_usage_pr_device.values()) for m in power_m]
        avg_w = sum(watts) / len(watts)
        
        avg_i = 0.0
        min_i = 0.0
        max_i = 0.0
        if intensity_m:
            ints = [m.carbon_intensity for m in intensity_m]
            avg_i = sum(ints) / len(ints)
            min_i = min(ints)
            max_i = max(ints)
            
        power_kwh = (avg_w / 1000.0) * duration_hours
        emissions_g = power_kwh * avg_i
        
        # power usage per device
        device_usage = {}
        for m in power_m:
            for c_name, c_power in m.power_usage_pr_device.items():
                if c_name not in device_usage:
                    device_usage[c_name] = 0.0
                device_usage[c_name] += c_power
                
        for c_name in device_usage:
            device_usage[c_name] /= len(power_m)
            
        return EventStatsData(
            avg_watt=avg_w,
            min_watt=min(watts),
            max_watt=max(watts),
            avg_intensity=avg_i,
            min_intensity=min_i,
            max_intensity=max_i,
            power_usage_pr_device=device_usage,
            emissions_g=emissions_g,
            power_usage_kwh=power_kwh,
            power_measurements_count=len(power_m),
            intensity_measurements_count=len(intensity_m)
        )
        
    def _update_predictions(self) -> None:
        p_config = self.session_config.prediction_config
        if not p_config or not p_config.enabled:
            return
            
        if self._completed_spans_count >= p_config.predict_after and p_config.total_units:
            remaining_epochs = p_config.total_units - self._completed_spans_count
            if remaining_epochs > 0:
                avg_power_per_epoch = self._cumulative_power_kwh / self._completed_spans_count
                avg_emissions_per_epoch = self._cumulative_emissions_g / self._completed_spans_count
                
                self._predicted_total_power_kwh = self._cumulative_power_kwh + (avg_power_per_epoch * remaining_epochs)
                self._predicted_total_emissions_g = self._cumulative_emissions_g + (avg_emissions_per_epoch * remaining_epochs)
            else:
                self._predicted_total_power_kwh = self._cumulative_power_kwh
                self._predicted_total_emissions_g = self._cumulative_emissions_g

    def _emit_session_stats(self) -> None:
        if self._power_measurements:
            current_w = sum(self._power_measurements[-1].power_usage_pr_device.values())
            device_usage = self._power_measurements[-1].power_usage_pr_device
        else:
            current_w = 0.0
            device_usage = {}
            
        current_i = self._intensity_measurements[-1].carbon_intensity if self._intensity_measurements else 0.0
        
        stats = SessionStatsData(
            current_wattage=current_w,
            current_intensity=current_i,
            total_emissions_g=self._cumulative_emissions_g,
            total_power_usage_kwh=self._cumulative_power_kwh,
            predicted_total_power_kwh=self._predicted_total_power_kwh,
            predicted_total_emissions_g=self._predicted_total_emissions_g,
            forecast_intensity=self._forecast_intensity,
            power_usage_pr_device=device_usage
        )
        event = SessionCurrentStatsEvent(timestamp=datetime.now(), stats=stats)
        for sink in self.event_sink:
            sink.put(event)
            
    def _cleanup_old_measurements(self) -> None:
        if not self._active_spans:
            if self._power_measurements:
                self._power_measurements = [self._power_measurements[-1]]
            if self._intensity_measurements:
                self._intensity_measurements = [self._intensity_measurements[-1]]
            return
            
        oldest_start = min(self._active_spans.values())
        self._power_measurements = [m for m in self._power_measurements if m.timestamp >= oldest_start]
        self._intensity_measurements = [m for m in self._intensity_measurements if m.timestamp >= oldest_start]
