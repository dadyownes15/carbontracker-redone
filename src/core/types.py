from dataclasses import dataclass
from enum import Enum
from typing import Union


class Component(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    RAM = "ram"


class BreachAction(str, Enum):
    """
    BreachAction describes the action executed by carbontracker on budget breach
        STOP: Stops the subprocess or training run by raising an error
        LOG: Logs a warning to the output event stream
        Callback: Calls the supplied Callback stream

    If callback function is supplied, it will overwrite the BreachAction to CALLBACK

    """

    LOG = "log"
    STOP = "stop"
    CALLBACK = "callback"
    PASS = "pass"


class IntensityMethod(str, Enum):
    """
    IntensityMethod describes the method which is used for fetch carbonintensity
        AUTO: Denotes automatically selects the best intensity estimate based on the config. API -> Location based average -> World Average
        ELECTRICITY_MAPS: Uses the electricityMaps API
        STATIC: Uses constant static input that must be supplied by the user
    """

    AUTO = "auto"
    ELECTRICITY_MAPS = "electricity_maps"
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
class ElectricityMapsGridZone:
    """
    ElectricityMapsGridZone - a specific id which aligns with the API of electricity maps allowing location specific fetching

    """

    zone_id: str  # e.g., 'DK-DK1' or 'US-CAL-CISO' useful for electricityMaps


@dataclass(frozen=True)
class CountryCode:
    country_code: str  # e.g., 'DK', 'US'


Location = GeoLocation | CloudRegion | ElectricityMapsGridZone | CountryCode
