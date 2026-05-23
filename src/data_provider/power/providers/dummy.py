from src.data_provider.power.power_measurement import PowerMeasurement
from src.data_provider.power.power_provider import PowerProvider
from datetime import datetime


class DummyGPU(PowerProvider):
    def __init__(self) -> None:
        super().__init__()
        pass
        
    def fetch(self) -> PowerMeasurement:
        return PowerMeasurement(
           timestamp=datetime.now(), 
           source="",
           wattage=50,
           device_id="GPU:0",
           pid=0,
        )

    def shutdown(self):
        pass

class DummyCPU(PowerProvider):
    def __init__(self) -> None:
        super().__init__()
        pass
        
    def fetch(self) -> PowerMeasurement:
        return PowerMeasurement(
           timestamp=datetime.now(), 
           source="",
           wattage=10,
           device_id="CPU:0",
           pid=0,
        )

    def shutdown(self):
        pass
