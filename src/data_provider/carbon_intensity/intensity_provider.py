
from abc import ABC
from typing import Union, Optional

from pydantic.dataclasses import dataclass
from typing_extensions import List

from src.core.config import IntensityMeasurementConfig
from src.data_provider.data_provider import DataProvider, MeasurementData


@dataclass(frozen=True)
class GeoLocation:
    latitude: float
    longitude: float

@dataclass(frozen=True)
class CloudRegion:
    provider: str  # e.g., 'aws', 'gcp', 'azure'
    region: str    # e.g., 'eu-west-1'

@dataclass(frozen=True)
class GridZone:
    zone_id: str   # e.g., 'DK-DK1' or 'US-CAL-CISO' useful for electricityMaps
    #

@dataclass(frozen=True)
class CountryCode:
    country_code: str # e.g., 'DK', 'US'

@dataclass(frozen=True)
class Location:
    data: Union[GeoLocation, CloudRegion, GridZone, CountryCode]

@dataclass(frozen=True)
class ResolvedLocation:
    """The canonical location resolved from config + environment."""
    location: Optional[Location]
    source: str # "config", "geolocation", "unknown"
    raw_input: Optional[str] = None

@dataclass(frozen=True)
class IntensityMeasurementData(MeasurementData):
    location: Location
    intensity: float                # usually Co2eq g / kwh
    is_prediction: bool

@dataclass(frozen=True)
class ResolutionStep:
    action: str          # e.g. "location_resolved", "api_key_found", "fallback_country"
    detail: str          # human-readable explanation
    level: str           # "info", "warning", "error"

from dataclasses import dataclass as std_dataclass

@std_dataclass(frozen=True)
class IntensityResolution:
    """Complete result of intensity provider factory resolution."""
    provider: DataProvider[IntensityMeasurementData]
    location: ResolvedLocation
    steps: List[ResolutionStep]