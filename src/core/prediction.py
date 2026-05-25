from typing import Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger("carbontracker.prediction")

class ForecastResult(BaseModel):
    """The expected carbon intensity for a future time window."""
    duration_s: float
    average_intensity_g_per_kwh: float 

class PredictionResult(BaseModel):
    completed_units: int
    total_units: int
    
    # Where we will end up
    estimated_duration_left_s: float
    projected_total_energy_kwh: float
    projected_total_emissions_g: float

class PredictionEngine:
    def __init__(self, total_units: int):
        self.total_units = total_units

    def predict(
        self, 
        completed_units: int,
        run_duration_s: float,
        current_cumulative_energy_kwh: float,
        current_cumulative_emissions_g: float,
        forecast: Optional[ForecastResult] = None
    ) -> Optional[PredictionResult]:
        
        if completed_units == 0:
            return None # Cannot predict yet
            
        # 1. What does ONE unit cost in terms of time and energy?
        avg_duration_per_unit = run_duration_s / completed_units
        avg_energy_per_unit = current_cumulative_energy_kwh / completed_units
        
        # 2. Base projection
        remaining_units = max(0, self.total_units - completed_units)
        estimated_duration_left = avg_duration_per_unit * remaining_units
        projected_remaining_energy = avg_energy_per_unit * remaining_units
        
        # 3. Emissions projection (Forecast vs Fallback)
        if forecast is not None:
            projected_remaining_emissions = projected_remaining_energy * forecast.average_intensity_g_per_kwh
        else:
            logger.warning("No forecast available. Falling back to extrapolating past emissions intensity.")
            avg_emissions_per_unit = current_cumulative_emissions_g / completed_units
            projected_remaining_emissions = avg_emissions_per_unit * remaining_units
        
        return PredictionResult(
            completed_units=completed_units,
            total_units=self.total_units,
            estimated_duration_left_s=estimated_duration_left,
            projected_total_energy_kwh=current_cumulative_energy_kwh + projected_remaining_energy,
            projected_total_emissions_g=current_cumulative_emissions_g + projected_remaining_emissions
        )
