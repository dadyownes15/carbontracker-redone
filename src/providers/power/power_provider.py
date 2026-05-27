from typing import Dict, Optional

from pydantic.dataclasses import dataclass

from src.providers.data_provider import MeasurementData


@dataclass(frozen=True)
class PowerMeasurementData(MeasurementData):
    component: str
    power_usage_pr_device: Dict[str, float]
    pid: Optional[int]
