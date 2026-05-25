import queue
import logging
from threading import Thread, Event
from typing import Dict, List, Optional, Callable
from datetime import datetime

from src.core.config import PredictionConfig, BudgetPolicy, SessionMode
from src.core.events import TrackerEvent, EventStart, EventStop, MeasurementEvent, EventStats, SessionCurrentStatsEvent, DiagnosticEvent, PredictionEvent, GuardEvent, LogSeverity
from src.core.stats import EventStatsData, SessionStatsData, SessionFinalStats
from src.data_provider.power.power_provider import PowerMeasurementData
from src.data_provider.carbon_intensity.intensity_provider import IntensityMeasurementData
from src.core.prediction import PredictionEngine, PredictionResult
from src.core.execution_guard import BudgetGuard, GuardVerdict
from src.core.emissions_calculations import compute_epoch_stats
from src.core.events import FinishedSession
from datetime import datetime
logger = logging.getLogger("carbontracker.aggregator")

class AggregatorThread(Thread):
    def __init__(
        self,
        prediction_config: PredictionConfig,
        budget_policy: Optional[BudgetPolicy],
        stats_emit_interval_s: float,
        mode: SessionMode,
        aggregation_queue: "queue.Queue[TrackerEvent]",
        event_sink: "List[queue.Queue[TrackerEvent]]",
        guard_callback: Optional[Callable[[GuardVerdict], None]] = None,
    ) -> None:
        super().__init__()
        self.aggregation_queue = aggregation_queue
        self.event_sink = event_sink
        self._mode = mode
        self._stats_emit_interval_s = stats_emit_interval_s
        self._guard_callback = guard_callback
        
        self._predict_after = prediction_config.predict_after if prediction_config.enabled else float('inf')
        self._prediction_engine = PredictionEngine(prediction_config.total_units) if prediction_config.enabled and prediction_config.total_units else None
        self._budget_guard = BudgetGuard(budget_policy) if budget_policy else None
        self._session_start_time: Optional[datetime] = None
        
        self._stop_event = Event()
        self.daemon = True
        self.name = "aggregator_thread"

        # Internal State
        self._active_spans: Dict[str, datetime] = {}
        self._power_measurements: List[PowerMeasurementData] = []
        self._intensity_measurements: List[IntensityMeasurementData] = []
        
        self._span_stats_history: List[EventStatsData] = []
        self._span_durations_s: List[float] = []
        
        # Cumulative Stats
        self._cumulative_emissions_g: float = 0.0
        self._cumulative_power_kwh: float = 0.0
        
        self._completed_root_spans_count: int = 0
        self._last_stats_emit = datetime.min
        
        # To store predictions
        self._last_prediction: Optional[PredictionResult] = None
        self._forecast_intensity: Optional[float] = None

    def stop(self) -> SessionFinalStats:
        self.aggregation_queue.put(None) 
        
        final_stats = SessionFinalStats(
            total_emissions_g=self._cumulative_emissions_g,
            total_power_usage_kwh=self._cumulative_power_kwh,
            duration_s=sum(self._span_durations_s),
            completed_spans_count=self._completed_root_spans_count
        )
        

        event = FinishedSession(timestamp=datetime.now(), stats=final_stats)
        self._emit_event(event)
            
        return final_stats

    def run(self) -> None:
        while True:
            try:
                event = self.aggregation_queue.get()
                if event is None:
                    break
                    
                if isinstance(event, EventStart):
                    self._handle_start(event)
                elif isinstance(event, EventStop):
                    self._handle_stop(event)
                elif isinstance(event, MeasurementEvent):
                    self._handle_measurement(event)
                    
            except Exception as e:
                logger.error(f"Aggregator encountered error processing event: {e}")

    def _emit_event(self, event: TrackerEvent) -> None:
        for sink in self.event_sink:
            sink.put(event)

    def _handle_start(self, event: EventStart) -> None:
        if self._session_start_time is None:
            self._session_start_time = event.started_at
            
        if self._active_spans:
            active_ids = list(self._active_spans.keys())
            logger.warning(
                f"Span '{event.span_id}' started while spans {active_ids} are still active. "
                f"Power measurements will be shared across overlapping spans — "
                f"per-span attribution is approximate."
            )
                
        self._active_spans[event.span_id] = event.started_at

    def _handle_measurement(self, event: MeasurementEvent) -> None:
        if isinstance(event.data, PowerMeasurementData):
            self._power_measurements.append(event.data)
        elif isinstance(event.data, IntensityMeasurementData):
            self._intensity_measurements.append(event.data)
            
        self._emit_event(event)
            
        self._emit_session_stats()

    def _handle_stop(self, event: EventStop) -> None:
        span_id = event.span_id
        if span_id not in self._active_spans:
            logger.warning("EventStop triggered, but could not find span_id in active spans")
            
        started_at = self._active_spans.pop(span_id)
        ended_at = event.ended_at
        
        event_stats_data = compute_epoch_stats(self._power_measurements, self._intensity_measurements, started_at, ended_at)
        
        stats_event = EventStats(
            span_id=span_id,
            started_at=started_at,
            ended_at=ended_at,
            stats=event_stats_data
        )
        self._emit_event(stats_event)

        # Only root-level spans count towards cumulative session totals and predictions
        if event.parent_span_id is None:
            self._cumulative_emissions_g += event_stats_data.emissions_g
            self._cumulative_power_kwh += event_stats_data.power_usage_kwh
            self._completed_root_spans_count += 1
            
            self._span_stats_history.append(event_stats_data)
            self._span_durations_s.append((ended_at - started_at).total_seconds())
            
            self._update_predictions(span_id, ended_at)
            
        # Emit global session stats
        self._emit_session_stats()
        
        # Memory cleanup
        self._cleanup_old_measurements()
        
        
    def _update_predictions(self, trigger_span_id: str, ended_at: datetime) -> None:
        if not self._prediction_engine or self._completed_root_spans_count < self._predict_after:
            return
            
        run_duration_s = (ended_at - self._session_start_time).total_seconds() if self._session_start_time else 0.0
            
        # TODO (dadyownes15): Implement ForecastResult generation
        prediction = self._prediction_engine.predict(
            completed_units=self._completed_root_spans_count,
            run_duration_s=run_duration_s,
            current_cumulative_energy_kwh=self._cumulative_power_kwh,
            current_cumulative_emissions_g=self._cumulative_emissions_g,
            forecast=None 
        )
        if not prediction:
            return
            
        self._last_prediction = prediction
        
        pred_event = PredictionEvent(
            created_at=datetime.now(),
            span_id=trigger_span_id,
            result=prediction
        )
        self._emit_event(pred_event)
            
        if self._budget_guard:
            verdict = self._budget_guard.check(prediction)
            
            if verdict.action != "pass":
                if self._mode.is_python and self._guard_callback:
                    self._guard_callback(verdict)
                elif self._mode.is_process:
                    guard_event = GuardEvent(
                        created_at=datetime.now(),
                        verdict=verdict,
                        prediction=prediction
                    )
                    self._emit_event(guard_event)

    def _emit_session_stats(self) -> None:
        now = datetime.now()
        if (now - self._last_stats_emit).total_seconds() < self._stats_emit_interval_s:
            return
        self._last_stats_emit = now
        
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
            power_usage_pr_device=device_usage
        )
        event = SessionCurrentStatsEvent(timestamp=now, stats=stats)
        self._emit_event(event)
            
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
