

from abc import abstractmethod
from typing import List
from src.data_provider.carbon_intensity.intensity_measurement import IntensityMeasurement, Location
from src.data_provider.data_provider import DataProvider

class IntensityProvider(DataProvider[IntensityMeasurement]):
    pass
class ForecastingIntensityProvider(IntensityProvider):
    @abstractmethod
    def get_forecast(self, hours: int) -> List[IntensityMeasurement]:
        pass