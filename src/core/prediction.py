from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel
import logging

from src.config.config import SessionConfig
from src.core.stats import SpanStats

logger = logging.getLogger("carbontracker.prediction")


class ForecastResult(BaseModel):
    duration_s: float
    average_intensity_g_per_kwh: float


class PredictionResult(BaseModel):
    completed_units: int | None = None
    total_units: int | None = None
    total_duration_s: float | None = None
    run_duration_s: float

    estimated_duration_left_s: float
    projected_total_energy_kwh: float
    projected_total_emissions_g: float


class PredictionMode(str, Enum):
    TIME = "time"
    UNIT = "unit"


class PredictionEngine:
    def __init__(
        self,
        total_units: int | None,
        unit_name: str | None,
        total_duration_s: int | None,
        run_duration_before_pred_s: int | None = None,
        predict_after_n_units: int | None = None,
        predict_interval_s: int | None = None,
    ):
        self.total_units = total_units
        self.total_duration_s = total_duration_s
        self.unit_of_interest = unit_name
        self.run_duration_before_pred_s = run_duration_before_pred_s
        self.predict_after_n_units = predict_after_n_units
        self.predict_interval_s = predict_interval_s
        self.mode: PredictionMode = self._define_mode(total_units, unit_name, total_duration_s)

        # Internal state:
        self._last_prediction_time: datetime | None = None

    @staticmethod
    def _define_mode(total_units,unit_name,total_duration) -> PredictionMode:
        if total_units is not None and unit_name is not None:
            return PredictionMode.UNIT
        elif total_duration is not None:
            return PredictionMode.TIME

        raise ValueError(
            "Cannot define prediction mode without total_units or total_duration."
        )

    def predict(
        self,
        span_stats: list[SpanStats],
        run_duration_s: float,
        current_cumulative_energy_kwh: float,
        current_cumulative_emissions_g: float,
        forecast: ForecastResult | None = None,
    ) -> PredictionResult:
        self._last_prediction_time = datetime.now()

        if self.mode == PredictionMode.UNIT:
            return self.predict_unit_based(
                span_stats,
                run_duration_s,
                current_cumulative_energy_kwh,
                current_cumulative_emissions_g,
                forecast,
            )
        else:
            return self.predict_time_based(
                run_duration_s,
                current_cumulative_energy_kwh,
                current_cumulative_emissions_g,
                forecast,
            )

    def should_predict(
        self,
        now: datetime,
        run_duration_s: float,
        spans: list[SpanStats]
    ) -> bool:
        # Stop if prediction_interval_s has not yet passed
        if (
            self.predict_interval_s is not None
            and self._last_prediction_time is not None
        ):
            since_last = (now - self._last_prediction_time).total_seconds()
            if since_last < self.predict_interval_s:
                return False

        if self.mode == PredictionMode.UNIT:
            # Check if the amount of spans with unit_of_interest satisfies the criteria
            if self.predict_after_n_units is not None:
                completed_units = sum(1 for s in spans if s.name == self.unit_of_interest)
                if completed_units < self.predict_after_n_units:
                    return False

        elif self.mode == PredictionMode.TIME:
            # check if run_duration is long enough
            if self.run_duration_before_pred_s is not None:
                if run_duration_s < self.run_duration_before_pred_s:
                    return False

        return True


    def predict_unit_based(
        self,
        span_stats: list[SpanStats],
        run_duration_s: float,
        current_cumulative_energy_kwh: float,
        current_cumulative_emissions_g: float,
        forecast: ForecastResult | None = None,
    ) -> PredictionResult:

        # We need to check the spans here
        completed_units = sum(1 for s in span_stats if s.name == self.unit_of_interest)
        
        if completed_units > 0:
            avg_duration_per_unit = run_duration_s / completed_units
            avg_energy_per_unit = current_cumulative_energy_kwh / completed_units
        else:
            avg_duration_per_unit = 0.0
            avg_energy_per_unit = 0.0


        remaining_units = max(0, self.total_units - completed_units)
        estimated_duration_left = avg_duration_per_unit * remaining_units
        projected_remaining_energy = avg_energy_per_unit * remaining_units

        if forecast is not None:
            projected_remaining_emissions = (
                projected_remaining_energy * forecast.average_intensity_g_per_kwh
            )
        else:
            logger.warning(
                "No forecast available. Falling back to extrapolating past emissions intensity."
            )
            if completed_units > 0:
                avg_emissions_per_unit = current_cumulative_emissions_g / completed_units
            else:
                avg_emissions_per_unit = 0.0
            projected_remaining_emissions = avg_emissions_per_unit * remaining_units

        return PredictionResult(
            completed_units=completed_units,
            total_units=self.total_units,
            run_duration_s=run_duration_s,
            estimated_duration_left_s=estimated_duration_left,
            projected_total_energy_kwh=current_cumulative_energy_kwh
            + projected_remaining_energy,
            projected_total_emissions_g=current_cumulative_emissions_g
            + projected_remaining_emissions,
        )

    def predict_time_based(
        self,
        run_duration_s: float,
        current_cumulative_energy_kwh: float,
        current_cumulative_emissions_g: float,
        forecast: ForecastResult | None = None,
    ) -> PredictionResult:

        if run_duration_s > 0:
            avg_energy_per_second = current_cumulative_energy_kwh / run_duration_s
        else:
            avg_energy_per_second = 0.0

        if self.total_duration_s is not None:
            remaining_duration_s = max(0.0, self.total_duration_s - run_duration_s)
        else:
            remaining_duration_s = 0.0
            
        projected_remaining_energy = avg_energy_per_second * remaining_duration_s

        if forecast is not None:
            projected_remaining_emissions = (
                projected_remaining_energy * forecast.average_intensity_g_per_kwh
            )
        else:
            logger.warning(
                "No forecast available. Falling back to extrapolating past emissions intensity."
            )
            if run_duration_s > 0:
                avg_emissions_per_second = current_cumulative_emissions_g / run_duration_s
            else:
                avg_emissions_per_second = 0.0
            projected_remaining_emissions = (
                avg_emissions_per_second * remaining_duration_s
            )

        return PredictionResult(
            total_duration_s=self.total_duration_s,
            run_duration_s=run_duration_s,
            estimated_duration_left_s=remaining_duration_s,
            projected_total_energy_kwh=current_cumulative_energy_kwh
            + projected_remaining_energy,
            projected_total_emissions_g=current_cumulative_emissions_g
            + projected_remaining_emissions,
        )
