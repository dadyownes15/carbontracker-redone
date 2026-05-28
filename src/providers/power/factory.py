import logging
from typing import List
import queue
from threading import Event

from src.core.exceptions import ProviderUnavailableError, ProviderPermissionError
from src.config.config import SessionConfig
from src.providers.data_provider_thread import DataProviderThread
from src.providers.power.power_provider import PowerMeasurementData
from src.core.events import TrackerEvent
from src.core.resolution import ResolutionStep, print_resolution_steps

from src.providers.power.providers.cpu.intel import IntelCPU
from src.providers.power.providers.cpu.generic import GenericCPU
from src.providers.power.providers.gpu.nvidia import NvidiaGPU
from src.providers.power.providers.apple_silicon.powermetrics import AppleSiliconCPU, AppleSiliconGPU, AppleSiliconANE


logger = logging.getLogger("carbontracker.power_factory")

def create_power_thread(
    config: SessionConfig, 
    aggregation_queue: "queue.Queue[TrackerEvent]", 
    notify_event: Event
) -> DataProviderThread[PowerMeasurementData]:
    
    providers = []
    pids = [int(pid) for pid in config.devices_by_pids] if config.devices_by_pids else []
    steps: List[ResolutionStep] = []
    
    # We no longer handle simulated components here natively based on a config flag.
    # The config components array drives real provider instantiation.
    component_names = [c.value.lower() for c in config.components]
    
    if "cpu" in component_names:
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
            
    if "gpu" in component_names:
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

    print_resolution_steps(steps, logger)

    print("Total providers: ", len(providers))
    return DataProviderThread(
        sample_interval=config.power_sampling_interval, 
        providers=providers, 
        aggregation_queue=aggregation_queue, 
        notify_event=notify_event
    )
