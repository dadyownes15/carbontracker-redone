from typing import Dict, Optional, Union

from pydantic.dataclasses import dataclass

from src.core.config import RealPowerMeasurementConfig, SimulatedPowerMeasurementConfig
from src.data_provider.data_provider import MeasurementData 

@dataclass(frozen=True)
class PowerMeasurementData(MeasurementData):
    component: str
    power_usage_pr_device: Dict[str,float]
    pid: Optional[int]

PowerMeasurementConfig = Union[RealPowerMeasurementConfig, SimulatedPowerMeasurementConfig]