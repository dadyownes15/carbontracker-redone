from abc import ABC
from datetime import datetime

from pydantic.dataclasses import dataclass

from src.data_provider.data_provider import MeasurementData, DataProvider 


@dataclass(frozen=True)
class PowerMeasurementData(MeasurementData):
    source_id: str
    wattage: float
    source: str
    device_id: str
    pid: int


class PowerProvider(DataProvider[PowerMeasurementData], ABC):
    pass