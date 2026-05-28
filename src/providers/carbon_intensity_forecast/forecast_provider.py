from dataclasses import dataclass
from datetime import datetime
from src.core.resolution import ResolutionStep
from src.core.types import Location
from src.providers.data_provider import DataProvider, MeasurementData
from src.providers.carbon_intensity.intensity_provider import ResolvedLocation

@dataclass(frozen=True)
class ForecastPoint:
    timestamp: datetime
    carbon_intensity: float

@dataclass(frozen=True)
class IntensityForecastData(MeasurementData):
    location: Location | None
    forecasts: list[ForecastPoint]

@dataclass(frozen=True)
class ForecastResolution:
    """Complete result of forecast provider factory resolution."""
    provider: DataProvider[IntensityForecastData]
    location: ResolvedLocation
    steps: list[ResolutionStep]
