from typing import Dict, Optional, List
from dataclasses import field
from datetime import datetime
from pydantic.dataclasses import dataclass

@dataclass(frozen=True)
class EventStatsData:
    """Stats calculated strictly for a specific span/epoch."""
    avg_watt: float
    min_watt: float
    max_watt: float
    avg_intensity: float
    min_intensity: float
    max_intensity: float
    power_usage_pr_device: Dict[str, float]
    emissions_g: float           # Emissions generated during this span
    power_usage_kwh: float       # Power consumed during this span
    power_measurements_count: int
    intensity_measurements_count: int

@dataclass(frozen=True)
class SessionStatsData:
    """Global stats reflecting the current state of the entire tracker session."""
    current_wattage: float
    current_intensity: float
    total_emissions_g: float     # Cumulative so far
    total_power_usage_kwh: float # Cumulative so far
    predicted_total_power_kwh: Optional[float] = None
    predicted_total_emissions_g: Optional[float] = None
    forecast_intensity: Optional[List[float]] = None
    power_usage_pr_device: Dict[str, float] = field(default_factory=dict)
