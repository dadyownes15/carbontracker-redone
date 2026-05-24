from threading import Thread, Event
from typing import Dict, List, Callable, Any, TypeVar, Generic
import time
from datetime import datetime

from src.core.config import ProviderConfig, PowerMeasurementConfig, IntensityMeasurementConfig, ProviderType
from src.data_provider.data_provider import MeasurementData
from src.data_provider.power.power_provider import PowerMeasurementData
from src.data_provider.carbon_intensity.intensity_provider import IntensityMeasurementData, Location, GridZone
from src.data_provider.power.providers.dummy import DummyCPU, DummyGPU
from src.data_provider.carbon_intensity.providers.dummy import DummyForecaster

TData = TypeVar('TData', bound=MeasurementData)

class BaseProviderThread(Thread, Generic[TData]):
    """
    Statically typed, autonomous base provider thread.
    """
    def __init__(self, sample_interval: float) -> None:
        super().__init__()
        self.sample_interval = sample_interval
        self._trigger_event = Event()
        self._stop_event = Event()
        self._fetch_done_event = None
        self.daemon = True

    def trigger_fetch(self) -> Event:
        """Wakes up the thread to do an immediate fetch and returns a completion event."""
        self._fetch_done_event = Event()
        self._trigger_event.set()
        return self._fetch_done_event

    def stop(self) -> None:
        self._stop_event.set()
        self._trigger_event.set()

    def run(self) -> None:
        self._work()
        while not self._stop_event.is_set():
            # Blocks until sample_interval passes (in-between fetch) OR trigger_event is set (forced fetch)
            self._trigger_event.wait(timeout=self.sample_interval)
            
            if self._stop_event.is_set():
                break
                
            self._trigger_event.clear()
            self._work()
            
            if self._fetch_done_event:
                self._fetch_done_event.set()
                self._fetch_done_event = None

    def _work(self) -> None:
        raise NotImplementedError("Subclasses must implement _work")


class PowerProviderThread(BaseProviderThread[PowerMeasurementData]):
    """
    Background polling loop for dummy CPU/GPU power. Appends directly to the handler's list.
    """
    def __init__(self, sample_interval: float, components: List[str], power_measurements: List[PowerMeasurementData]) -> None:
        super().__init__(sample_interval)
        self.power_measurements = power_measurements
        self.providers = []
        if "cpu" in components:
            self.providers.append(DummyCPU())
        if "gpu" in components:
            self.providers.append(DummyGPU())

    def _work(self) -> None:
        for provider in self.providers:
            try:
                measurement: PowerMeasurementData = provider.fetch()
                self.power_measurements.append(measurement)
            except Exception:
                pass


class IntensityProviderThread(BaseProviderThread[IntensityMeasurementData]):
    """
    Background polling loop for dummy carbon intensity. Appends directly to the handler's list.
    """
    def __init__(self, sample_interval: float, location_str: str, intensity_measurements: List[IntensityMeasurementData]) -> None:
        super().__init__(sample_interval)
        self.intensity_measurements = intensity_measurements
        self.location = Location(data=GridZone(zone_id=location_str))
        self.provider = DummyForecaster(location=self.location)
        self._last_api_call = 0.0
        self.cache_duration = 900.0  # 15 minutes API cool-down

    def _work(self) -> None:
        now = time.time()
        
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
            measurement: IntensityMeasurementData = self.provider.fetch()
            self._last_api_call = now
            self.intensity_measurements.append(measurement)
        except Exception:
            pass


# --- Factory Creation Dispatcher ---

def create_power_thread(config: PowerMeasurementConfig, power_measurements: List[PowerMeasurementData]) -> PowerProviderThread:
    return PowerProviderThread(config.sample_interval, config.components, power_measurements)

def create_intensity_thread(config: IntensityMeasurementConfig, intensity_measurements: List[IntensityMeasurementData]) -> IntensityProviderThread:
    return IntensityProviderThread(config.sample_interval, config.location or "US", intensity_measurements)

CREATORS: Dict[ProviderType, Callable[[Any, List[Any]], BaseProviderThread]] = {
    ProviderType.POWER: lambda c, l: create_power_thread(c, l),
    ProviderType.INTENSITY: lambda c, l: create_intensity_thread(c, l),
}

def provider_factory(config: ProviderConfig, measurements: List[Any]) -> BaseProviderThread:
    prov_type = config.provider_type
    if prov_type not in CREATORS:
        raise ValueError(f"Unknown provider config type: {prov_type}")
    return CREATORS[prov_type](config, measurements)
