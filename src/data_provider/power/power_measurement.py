from pydantic.dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class PowerMeasurement:
    timestamp: datetime 
    pid: int  
    wattage: float
    source: str
    device_id: str
