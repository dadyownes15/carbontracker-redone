
from typing import List

from src.data_provider.data_provider import DataProvider
from src.data_provider.data_provider_thread import ProviderThread
from src.data_provider.power.power_provider import PowerMeasurementData

class PowerProviderThread(ProviderThread[PowerMeasurementData]):
    """
    Background polling loop for dummy CPU/GPU power. Appends directly to the handler's list.
    """
    def __init__(self, 
        sample_interval: float, 
        power_measurements: List[PowerMeasurementData],
        providers: List[DataProvider[PowerMeasurementData]]
    ) -> None:
        super().__init__(sample_interval,providers)
        self.power_measurements = power_measurements

    def _work(self) -> None:
        for provider in self.providers:
            try:
                measurement: PowerMeasurementData = provider.fetch()
                self.power_measurements.append(measurement)
            except Exception:
                pass
