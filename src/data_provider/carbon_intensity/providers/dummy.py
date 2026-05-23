import math
from datetime import datetime, timedelta
from typing import List
from src.data_provider.carbon_intensity.intensity_measurement import IntensityMeasurement, Location
from src.data_provider.carbon_intensity.intensity_provider import ForecastingIntensityProvider

class DummyForecaster(ForecastingIntensityProvider):
    """
    A simulated carbon intensity provider.
    Satisfies IntensityProvider.location via a simple instance attribute.
    """
    
    def __init__(self, location: Location, base_intensity: float = 400.0):
        # This instance variable satisfies the @property @abstractmethod in the base class
        self.location = location
        self.base_intensity = base_intensity

    def fetch(self) -> IntensityMeasurement:
        """Returns the current simulated intensity."""
        return self._generate(datetime.now(), is_prediction=False)

    def get_forecast(self, hours: int) -> List[IntensityMeasurement]:
        """Generates a list of future measurements for the next N hours."""
        return [
            self._generate(datetime.now() + timedelta(hours=h), is_prediction=True)
            for h in range(1, hours + 1)
        ]

    def shutdown(self) -> None:
        """No hardware or API connections to close for the dummy."""
        pass

    def _generate(self, time: datetime, is_prediction: bool) -> IntensityMeasurement:
        """
        Internal logic to create a measurement based on a 24-hour sine wave.
        Dips at 12:00 (high renewables/solar), peaks at 00:00.
        """
        
        cycle = math.cos(2 * math.pi * (time.hour - 12) / 24)
        variation = (self.base_intensity * 0.25) * cycle
        current_intensity = self.base_intensity + variation

        return IntensityMeasurement(
            timestamp=time,
            location=self.location,
            intensity=round(current_intensity, 2),
            is_prediction=is_prediction
        )