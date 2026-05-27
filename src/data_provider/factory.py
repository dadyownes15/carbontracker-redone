import logging
from typing import List

from src.core.exceptions import ProviderUnavailableError, ProviderPermissionError

from src.core.config import ProviderConfig, PowerMeasurementConfig, ProviderType
from src.data_provider.data_provider_thread import DataProviderThread, TData
from src.data_provider.carbon_intensity.intensity_provider import IntensityMeasurementData
from src.data_provider.carbon_intensity.factory import create_intensity_thread
from src.data_provider.power.power_provider import PowerMeasurementData
from src.core.events import TrackerEvent
import queue
from threading import Event

from src.data_provider.power.providers.cpu.sim_cpu import SimulatedCPUProvider
from src.data_provider.power.providers.gpu.sim_gpu import SimulatedGPUProvider
from src.data_provider.power.providers.cpu.intel import IntelCPU
from src.data_provider.power.providers.cpu.generic import GenericCPU
from src.data_provider.power.providers.gpu.nvidia import NvidiaGPU
from src.data_provider.power.providers.apple_silicon.powermetrics import AppleSiliconCPU, AppleSiliconGPU, AppleSiliconANE
from src.core.config import RealPowerMeasurementConfig, SimulatedPowerMeasurementConfig


from src.core.resolution import ResolutionStep

logger = logging.getLogger("carbontracker.power_factory")

# --- Factory Creation Dispatcher ---
def create_power_thread(config: PowerMeasurementConfig, aggregation_queue: "queue.Queue[TrackerEvent]", notify_event: Event) -> DataProviderThread[PowerMeasurementData]:
    print("Creating a prower thread")
    if isinstance(config, SimulatedPowerMeasurementConfig):
        providers = []
        for comp in config.simulated_components:
            if "cpu" in comp.name.lower():
                providers.append(SimulatedCPUProvider(comp.name, comp.power_draw_w))
            else:
                providers.append(SimulatedGPUProvider(comp.name, comp.power_draw_w))
                
        return DataProviderThread(config.sample_interval, providers, aggregation_queue, notify_event)

    if isinstance(config, RealPowerMeasurementConfig):
        providers = []
        pids = [int(pid) for pid in config.devices_by_pids] if config.devices_by_pids else []
        steps: List[ResolutionStep] = []
        
        if "cpu" in config.components:
            for cls in [IntelCPU, AppleSiliconCPU, GenericCPU]:
                try:
                    cpu_provider = cls(pids=pids)
                    steps.append(ResolutionStep("provider_resolved", f"CPU: {cpu_provider.name}", "success"))
                    providers.append(cpu_provider)
                    break
                except (ProviderPermissionError, ProviderUnavailableError):
                    continue
            else:
                steps.append(ResolutionStep("no_provider", "No CPU provider available", "warning"))
                
        if "gpu" in config.components:
            for cls in [NvidiaGPU, AppleSiliconGPU]:
                try:
                    gpu_provider = cls(pids=pids)
                    steps.append(ResolutionStep("provider_resolved", f"GPU: {gpu_provider.name}", "success"))
                    providers.append(gpu_provider)
                    break
                except (ProviderPermissionError, ProviderUnavailableError):
                    continue
            else:
                steps.append(ResolutionStep("no_provider", "No GPU provider available", "warning"))
            
            try:
                ane_provider = AppleSiliconANE(pids=pids)
                steps.append(ResolutionStep("provider_resolved", f"ANE: {ane_provider.name}", "success"))
                providers.append(ane_provider)
            except (ProviderPermissionError, ProviderUnavailableError):
                pass

        # Print the resolution log
        for step in steps:
            if step.level == "success":
                logger.info(f"{step.detail}")
            elif step.level == "warning":
                logger.warning(f" {step.detail}")
            else:
                logger.info(f"{step.detail}")

        print("Total providers: ", len(providers))
        return DataProviderThread(config.sample_interval, providers, aggregation_queue, notify_event)
        
    else:
        raise ValueError("Unrecognized method detected in power provider thread creation")


# create_intensity_thread is now imported from src.data_provider.carbon_intensity.factory

def provider_factory(config: ProviderConfig, aggregation_queue: "queue.Queue[TrackerEvent]", notify_event: Event) -> DataProviderThread[TData]:
    prov_type = config.provider_type

    if prov_type == ProviderType.INTENSITY:
        return create_intensity_thread(config=config, aggregation_queue=aggregation_queue, notify_event=notify_event)
    elif prov_type == ProviderType.POWER:
        return create_power_thread(config=config, aggregation_queue=aggregation_queue, notify_event=notify_event)
    else:
        raise ValueError("Unknown provider type")
