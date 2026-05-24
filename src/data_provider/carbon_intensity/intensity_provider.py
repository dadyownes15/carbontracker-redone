
from abc import ABC
from datetime import datetime
from typing import Union

from pydantic.dataclasses import dataclass

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
class Location:
    data: Union[GeoLocation, CloudRegion, GridZone]


@dataclass(frozen=True)
class IntensityMeasurementData(MeasurementData):
    location: Location
    intensity: float                # usually Co2eq g / kwh
    is_prediction: bool


class IntensityProvider(DataProvider[IntensityMeasurementData],ABC):
    pass
