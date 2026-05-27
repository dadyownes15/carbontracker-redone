
from abc import ABC
from typing import Union, Optional

from pydantic.dataclasses import dataclass
from typing_extensions import List

from src.core.config import IntensityMeasurementConfig, Location
from src.providers.data_provider import DataProvider, MeasurementData


@dataclass(frozen=True)
class ResolvedLocation:
    """The canonical location resolved from config + environment."""
    location: Optional[Location]
    source: str # "config", "geolocation", "unknown"
    raw_input: Optional[str] = None

@dataclass(frozen=True)
class IntensityMeasurementData(MeasurementData):
    location: Optional[Location]
    carbon_intensity: float                # usually Co2eq g / kwh
    is_prediction: bool

from src.core.resolution import ResolutionStep

from dataclasses import dataclass as std_dataclass

@std_dataclass(frozen=True)
class IntensityResolution:
    """Complete result of intensity provider factory resolution."""
    provider: DataProvider[IntensityMeasurementData]
    location: ResolvedLocation
    steps: List[ResolutionStep]
