from dataclasses import dataclass
from enum import Enum
from typing import Union

# In Python 3.11+, StrEnum is available, but Enum with str mixin works for >=3.10
class Component(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    RAM = "ram"

class BreachAction(str, Enum):
    LOG = "log"
    STOP = "stop"
    CALLBACK = "callback"

class IntensityMethod(str, Enum):
    AUTO = "auto"
    ELECTRICITY_MAPS = "electricityMaps"
    STATIC = "static"


@dataclass(frozen=True)
class GeoLocation:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class CloudRegion:
    provider: str  # e.g., 'aws', 'gcp', 'azure'
    region: str  # e.g., 'eu-west-1'


@dataclass(frozen=True)
class GridZone:
    zone_id: str  # e.g., 'DK-DK1' or 'US-CAL-CISO' useful for electricityMaps


@dataclass(frozen=True)
class CountryCode:
    country_code: str  # e.g., 'DK', 'US'


Location = Union[GeoLocation, CloudRegion, GridZone, CountryCode]
