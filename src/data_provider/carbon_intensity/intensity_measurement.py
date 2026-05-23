
from typing import Union
from pydantic.dataclasses import dataclass
from datetime import datetime

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
class IntensityMeasurement:
    timestamp: datetime
    location: Location 
    intensity: float                # usually Co2eq g / kwh
    is_prediction: bool 
    
    
    