from threading import Thread, Event
from typing import Dict, List, Callable, Any, TypeVar, Generic
import time
from datetime import datetime

from src.core.config import ProviderConfig, PowerMeasurementConfig, IntensityMeasurementConfig, ProviderType
from src.data_provider.power.power_provider import PowerMeasurementData
from src.data_provider.carbon_intensity.intensity_provider import IntensityMeasurementData
from src.data_provider.carbon_intensity.providers.dummy import DummyForecaster


# --- Factory Creation Dispatcher ---
def create_power_thread(config: PowerMeasurementConfig, power_measurements: List[PowerMeasurementData]) -> PowerProviderThread:
    return PowerProviderThread(config.sample_interval, config.components, power_measurements)

def create_intensity_thread(config: IntensityMeasurementConfig, intensity_measurements: List[IntensityMeasurementData]) -> IntensityProviderThread:
    return IntensityProviderThread(config.sample_interval, config.location or "US", intensity_measurements)

CREATORS: Dict[ProviderType, Callable[[Any, List[Any]], ProviderThread]] = {
    ProviderType.POWER: lambda c, l: create_power_thread(c, l),
    ProviderType.INTENSITY: lambda c, l: create_intensity_thread(c, l),
}

def provider_factory(config: ProviderConfig, measurements: List[Any]) -> ProviderThread:
    prov_type = config.provider_type
    if prov_type not in CREATORS:
        raise ValueError(f"Unknown provider config type: {prov_type}")
    return CREATORS[prov_type](config, measurements)
