from datetime import datetime
from src.providers.data_provider import DataProvider
from src.providers.power.power_provider import PowerMeasurementData


class DummyGPU(DataProvider[PowerMeasurementData]):
    def __init__(self, pids=None) -> None:
        super().__init__()
        
    @property
    def name(self) -> str:
        return "Dummy GPU"

    def fetch(self) -> PowerMeasurementData:
        return PowerMeasurementData(
            timestamp=datetime.now(),
            component="gpu",
            power_usage_pr_device={"GPU:0": 50.0},
            pid=None,
        )

    def shutdown(self) -> None:
        pass


class DummyCPU(DataProvider[PowerMeasurementData]):
    def __init__(self, pids=None) -> None:
        super().__init__()
        
    @property
    def name(self) -> str:
        return "Dummy CPU"

    def fetch(self) -> PowerMeasurementData:
        return PowerMeasurementData(
            timestamp=datetime.now(),
            component="cpu",
            power_usage_pr_device={"CPU:0": 10.0},
            pid=None,
        )

    def shutdown(self) -> None:
        pass