from datetime import datetime
from time import time
from src.data_provider.power.power_provider import PowerMeasurementData, PowerProvider


class DummyGPU(PowerProvider):
    def __init__(self) -> None:
        super().__init__()
        
    def fetch(self) -> PowerMeasurementData:
        return PowerMeasurementData(
            timestamp=datetime.now(),
            source_id="GPU:0",
            wattage=50.0,
            source="nvidia-smi",  # Added a mock source for realism
            device_id="GPU:0",
            pid=0,
        )

    def shutdown(self) -> None:
        pass


class DummyCPU(PowerProvider):
    def __init__(self) -> None:
        super().__init__()
        
    def fetch(self) -> PowerMeasurementData:
        # Changed from returning PowerMeasurement to PowerMeasurementData
        return PowerMeasurementData(
            timestamp=datetime.now(),
            source_id="CPU:0",
            wattage=10.0,
            source="intel-rapl",  # Added a mock source for realism
            device_id="CPU:0",
            pid=0,
        )

    def shutdown(self) -> None:
        pass