import logging
from typing import List

from src.core.exceptions import ProviderUnavailableError, ProviderPermissionError

from src.core.config import ProviderConfig, IntensityMeasurementConfig, ProviderType
from src.data_provider.data_provider_thread import DataProviderThread, TData
from src.data_provider.carbon_intensity.intensity_provider import IntensityMeasurementData
from src.data_provider.carbon_intensity.factory import create_intensity_thread
from src.data_provider.power.power_provider import PowerMeasurementConfig, PowerMeasurementData

from src.data_provider.power.providers.cpu.sim_cpu import SimulatedCPUProvider
from src.data_provider.power.providers.gpu.sim_gpu import SimulatedGPUProvider
from src.data_provider.power.providers.cpu.intel import IntelCPU
from src.data_provider.power.providers.cpu.generic import GenericCPU
from src.data_provider.power.providers.gpu.nvidia import NvidiaGPU
from src.data_provider.power.providers.apple_silicon.powermetrics import AppleSiliconCPU, AppleSiliconGPU
from src.core.config import RealPowerMeasurementConfig, SimulatedPowerMeasurementConfig


logger = logging.getLogger("carbontracker.power_factory")

# --- Factory Creation Dispatcher ---
def create_power_thread(config: PowerMeasurementConfig, power_measurements: List[PowerMeasurementData]) -> DataProviderThread[PowerMeasurementData]:
    if isinstance(config, SimulatedPowerMeasurementConfig):
        providers = []
        for comp in config.simulated_components:
            if "cpu" in comp.name.lower():
                providers.append(SimulatedCPUProvider(comp.name, comp.power_draw_w))
            else:
                providers.append(SimulatedGPUProvider(comp.name, comp.power_draw_w))
                
        return DataProviderThread(config.sample_interval, providers, power_measurements)

    if isinstance(config, RealPowerMeasurementConfig):
        providers = []
        pids = [int(pid) for pid in config.devices_by_pids] if config.devices_by_pids else []
        
        if "cpu" in config.components:
            cpu_provider = None
            for cls in [IntelCPU, AppleSiliconCPU, GenericCPU]:
                try:
                    cpu_provider = cls(pids=pids)
                    break
                except ProviderPermissionError as e:
                    logger.warning(f"{cls.__name__} permission denied: {e}. Trying fallback.")
                except ProviderUnavailableError as e:
                    logger.info(f"{cls.__name__} unavailable: {e}. Trying fallback.")
            if cpu_provider:
                providers.append(cpu_provider)
                
        if "gpu" in config.components:
            gpu_provider = None
            for cls in [NvidiaGPU, AppleSiliconGPU]:
                try:
                    gpu_provider = cls(pids=pids)
                    break
                except ProviderPermissionError as e:
                    logger.warning(f"{cls.__name__} permission denied: {e}. Trying fallback.")
                except ProviderUnavailableError as e:
                    logger.info(f"{cls.__name__} unavailable: {e}. Trying fallback.")
            if gpu_provider:
                providers.append(gpu_provider)

        return DataProviderThread(config.sample_interval, providers, power_measurements)
        
    else:
        raise ValueError("Unrecognized method detected in power provider thread creation")


# create_intensity_thread is now imported from src.data_provider.carbon_intensity.factory

def provider_factory(config: ProviderConfig, measurements: List[TData]) -> DataProviderThread[TData]:
    prov_type = config.provider_type

    if prov_type == ProviderType.INTENSITY:
        return create_intensity_thread(config=config, intensity_measurements=measurements)
    elif prov_type == ProviderType.POWER:
        return create_power_thread(config=config, power_measurements=measurements)
    else:
        raise ValueError("Unknown provider type")
