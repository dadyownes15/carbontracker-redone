
from datetime import datetime

from typing_extensions import List
import time
from src.data_provider.carbon_intensity.intensity_provider import IntensityMeasurementData
from src.data_provider.data_provider import DataProvider
from src.data_provider.data_provider_thread import ProviderThread


class IntensityProviderThread(ProviderThread[IntensityMeasurementData]):
    """
    Background polling loop for dummy carbon intensity. Appends directly to the handler's list.
    """
    def __init__(self, sample_interval: float,
        location_str: str,
        providers: List[DataProvider[IntensityMeasurementData]],
        intensity_measurements: List[IntensityMeasurementData]
    ) -> None:
        super().__init__(sample_interval,providers)
        self.intensity_measurements = intensity_measurements
        self._last_api_call = 0.0
        self.cache_duration = 900.0  # 15 minutes API cool-down

        assert len(providers), "Aggregation over multiple dataproviders for intensity measurements is not yet implemented"
        
    def _work(self) -> None:
        now = time.time()
        
        # TODO (dadyownes15): Improve stamping logic
        # Caching logic: If triggered too quickly, reuse the last real API value 
        # but stamp it with the current time to maintain the profile timeline.
        if self._last_api_call > 0 and (now - self._last_api_call) < self.cache_duration:
            if self.intensity_measurements:
                last_val = self.intensity_measurements[-1]
                cached_measurement = IntensityMeasurementData(
                    timestamp=datetime.now(),
                    location=last_val.location,
                    intensity=last_val.intensity,
                    is_prediction=last_val.is_prediction
                )
                self.intensity_measurements.append(cached_measurement)
            return

        try:
            # TODO (dadyownes15): average over different intensity fetches
            measurement: IntensityMeasurementData = self.providers[0].fetch()
            self._last_api_call = now
            self.intensity_measurements.append(measurement)
        except Exception:
            pass

