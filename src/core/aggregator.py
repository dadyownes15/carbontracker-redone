from multiprocessing import Value
import queue
import logging
from threading import Thread, Event
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

from src.config.config import SessionConfig, SessionMode
from src.core.events import (
    TrackerEvent,
    EventStart,
    EventStop,
    MeasurementEvent,
    EventStats,
    SessionCurrentStatsEvent,
    DiagnosticEvent,
    PredictionEvent,
    GuardEvent,
    LogSeverity,
)
from src.core.stats import SpanStats, SessionStatsData, SessionFinalStats
from src.providers.data_provider import MeasurementData
from src.providers.power.power_provider import PowerMeasurementData
from src.providers.carbon_intensity.intensity_provider import (
    IntensityMeasurementData,
)
from src.core.prediction import ForecastResult, PredictionEngine, PredictionResult
from src.core.execution_guard import BudgetGuard, GuardVerdict
from src.core.emissions_calculations import compute_epoch_stats
from src.core.events import FinishedSession

logger = logging.getLogger("carbontracker.aggregator")


class AggregatorThread(Thread):
    def __init__(
        self,
        session_config: SessionConfig,
        session_stats_interval_s: int,

        aggregation_queue: queue.Queue[TrackerEvent],
        event_sink: list[queue.Queue[TrackerEvent]],
        prediction_engine: PredictionEngine | None = None,
        budget_guard: BudgetGuard | None = None,
    ) -> None:
        super().__init__()
        self.aggregation_queue = aggregation_queue
        self.event_sink = event_sink
        self._prediction_engine = prediction_engine
        self._budget_guard = budget_guard

        # Thread info
        self.daemon = True
        self.name = "aggregator_thread"


        # Settings
        self.session_stats_interval_s: int = session_stats_interval_s
        # Internal State
        self._active_spans: dict[str, datetime] = {}
        self._power_measurements: list[PowerMeasurementData] = []
        self._intensity_measurements: list[IntensityMeasurementData] = []
        self._forecasts: list[ForecastResult]
        self._session_start_time: datetime = datetime.now()
        self._span_stats_history: list[SpanStats] = []
        self._span_durations_s: list[float] = []
        self._last_stats_emit: datetime = datetime.min

        # Cumulative Stats
        self._cumulative_emissions_g: float = 0.0
        self._cumulative_power_kwh: float = 0.0
        self._completed_root_spans_count: int = 0


    def stop(self) -> SessionFinalStats:
        self.aggregation_queue.put(None)

        final_stats = SessionFinalStats(
            total_emissions_g=self._cumulative_emissions_g,
            total_power_usage_kwh=self._cumulative_power_kwh,
            duration_s=sum(self._span_durations_s),
            completed_spans_count=self._completed_root_spans_count,
        )

        event = FinishedSession(timestamp=datetime.now(), stats=final_stats)
        self._emit_event(event)

        return final_stats

    def run(self) -> None:
        # Create a start event here
        while True:
            try:
                event = self.aggregation_queue.get(timeout=self.session_stats_interval_s)
                if event is None:
                    break

                if isinstance(event, EventStart):
                    self._handle_start(event)

                elif isinstance(event, EventStop):
                    self._handle_stop(event)

                elif isinstance(event, MeasurementEvent):
                    self._handle_measurement(event)

            except queue.Empty:
                self._emit_session_stats()
                self._update_predictions()

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

    def _handle_measurement(self, event: MeasurementEvent[Any]) -> None:
        if isinstance(event.data, PowerMeasurementData):
            self._power_measurements.append(event.data)
        elif isinstance(event.data, IntensityMeasurementData):
            self._intensity_measurements.append(event.data)
        else: 
            logger.error("Unknown measurement event:\n", event)

        self._emit_event(event)

    def _handle_stop(self, event: EventStop) -> None:
        span_id = event.span_id
        if span_id not in self._active_spans:
            logger.error(
                "EventStop triggered, but could not find span_id in active spans"
            )

        started_at = self._active_spans.pop(span_id)
        ended_at = event.ended_at

        event_stats_data = compute_epoch_stats(
            self._power_measurements, self._intensity_measurements, started_at, ended_at
        )

        stats_event = EventStats(
            span_id=span_id,
            started_at=started_at,
            ended_at=ended_at,
            stats=event_stats_data,
        )

        self._emit_event(stats_event)
        
        # Accumalating the span stats here, why do we do this? 
        self._span_stats_history.append(event_stats_data)

       # Memory cleanup
        self._cleanup_old_measurements()

    
    def _update_predictions(self) -> None:
        
        # Stop if no prediction engine present
        if self._prediction_engine is None:
            return

        now = datetime.now()
        run_duration_s = (now - self._session_start_time).total_seconds() 

       
        should_predict = self._prediction_engine.should_predict(now=now, run_duration_s=run_duration_s, spans=self._span_stats_history)

        if not should_predict:
            return

        # TODO (dadyownes15): Implement ForecastResult generation
        prediction = self._prediction_engine.predict(
            span_stats=self._span_stats_history,
            run_duration_s=run_duration_s,
            current_cumulative_energy_kwh=self._cumulative_power_kwh,
            current_cumulative_emissions_g=self._cumulative_emissions_g,
        )


        pred_event = PredictionEvent(
            created_at=datetime.now(),  result=prediction)
        self._emit_event(pred_event)
        
        # Only trigger guard on prediction events, if we use the predicted values
        if self._budget_guard is not None and self._budget_guard.use_predicted_values:
            self._check_guard(prediction=prediction)

    def _emit_session_stats(self) -> None:
        if (not self._power_measurements) or (not self._intensity_measurements):
            return
        now = datetime.now()
        time_since_last_update_s = (now - self._last_stats_emit).total_seconds() 
        if  time_since_last_update_s < self._emit_session_stats_interval_s
            return

        self._last_stats_emit = now


        if self._power_measurements:
            current_w = sum(self._power_measurements[-1].power_usage_pr_device.values())
            device_usage = self._power_measurements[-1].power_usage_pr_device
        else:
            current_w = 0.0
            device_usage = {}

        current_i = (
            self._intensity_measurements[-1].carbon_intensity
            if self._intensity_measurements
            else 0.0
        )
       
        #TODO: Update this to be a weighted average, by reusing the calculation
        power_usage_kwh_since_last_update = time_since_last_update_s*current_w
        emissions_g_since_last_update = power_usage_kwh_since_last_update * current_i  
    
        self._cumulative_power_kwh += power_usage_kwh_since_last_update
        self._cumulative_emissions_g += emissions_g_since_last_update

        stats = SessionStatsData(
            current_wattage=current_w,
            current_intensity=current_i,
            total_emissions_g=self._cumulative_emissions_g,
            total_power_usage_kwh=self._cumulative_power_kwh,
            power_usage_pr_device=device_usage,
        )
        event = SessionCurrentStatsEvent(timestamp=now, stats=stats)
        self._emit_event(event)

        if self._budget_guard is not None and not self._budget_guard.use_predicted_values:
            self._check_guard(prediction=None)

    def _check_guard(self, prediction: PredictionResult | None = None) -> None:
        if self._budget_guard is None:
            return
            
        verdict = self._budget_guard.check(
            cumulative_energy_kwh=self._cumulative_power_kwh,
            cumulative_emissions_g=self._cumulative_emissions_g,
            prediction=prediction
        )
        guard_event = GuardEvent(
            created_at=datetime.now(),
            verdict=verdict,
            prediction=prediction,
        )
        self._emit_event(guard_event)

    def _cleanup_old_measurements(self) -> None:
        if not self._active_spans:
            if self._power_measurements:
                self._power_measurements = [self._power_measurements[-1]]
            if self._intensity_measurements:
                self._intensity_measurements = [self._intensity_measurements[-1]]
            return

        oldest_start = min(self._active_spans.values())
        self._power_measurements = [
            m for m in self._power_measurements if m.timestamp >= oldest_start
        ]
        self._intensity_measurements = [
            m for m in self._intensity_measurements if m.timestamp >= oldest_start
        ]

