import platform
import subprocess
import re
import time
from datetime import datetime
from typing import Union, List, Pattern

from src.data_provider.data_provider import DataProvider
from src.data_provider.power.power_provider import PowerMeasurementData
from src.core.exceptions import ProviderUnavailableError


class PowerMetricsUnified:
    _output: Union[None, str] = None
    _last_updated: Union[None, float] = None

    @staticmethod
    def get_output():
        if (
            PowerMetricsUnified._output is None
            or PowerMetricsUnified._last_updated is None
            or time.time() - PowerMetricsUnified._last_updated > 1
        ):
            PowerMetricsUnified._output = subprocess.check_output(
                [
                    "sudo",
                    "powermetrics",
                    "-n",
                    "1",
                    "-i",
                    "100",
                    "--samplers",
                    "all",
                ],
                universal_newlines=True,
                stderr=subprocess.DEVNULL,
            )
            PowerMetricsUnified._last_updated = time.time()
        return PowerMetricsUnified._output


class AppleSiliconCPU(DataProvider[PowerMeasurementData]):
    def __init__(self, pids: List[int]):
        self.pids = pids
        if platform.system() != "Darwin":
            raise ProviderUnavailableError("Apple Silicon providers are only available on macOS (Darwin).")
        
        self.cpu_pattern = re.compile(r"CPU Power: (\d+) mW")

    @property
    def name(self) -> str:
        return "Apple Silicon CPU"

    def fetch(self) -> PowerMeasurementData:
        output = PowerMetricsUnified.get_output()
        cpu_power = self.parse_power(output, self.cpu_pattern)
        
        return PowerMeasurementData(
            timestamp=datetime.now(),
            component="cpu",
            power_usage_pr_device={"CPU": cpu_power},
            pid=None
        )

    def parse_power(self, output: str, pattern: Pattern[str]) -> float:
        match = pattern.search(output)
        if match:
            power = float(match.group(1)) / 1000  # Convert mW to W
            return power
        else:
            return 0.0

    def shutdown(self):
        pass


class AppleSiliconGPU(DataProvider[PowerMeasurementData]):
    def __init__(self, pids: List[int]):
        self.pids = pids
        if platform.system() != "Darwin":
            raise ProviderUnavailableError("Apple Silicon providers are only available on macOS (Darwin).")

        self.gpu_pattern = re.compile(r"GPU Power: (\d+) mW")
        self.ane_pattern = re.compile(r"ANE Power: (\d+) mW")

    @property
    def name(self) -> str:
        return "Apple Silicon GPU"

    def fetch(self) -> PowerMeasurementData:
        output = PowerMetricsUnified.get_output()
        gpu_power = self.parse_power(output, self.gpu_pattern)
        ane_power = self.parse_power(output, self.ane_pattern)
        
        # Original code added them together, but we can return them separately or together.
        # Following original behavior of returning [gpu_power + ane_power] for "GPU" and "ANE".
        # We will split it into a dict for better tracking if desired, or keep it combined.
        # Let's track them explicitly per device if we want to be accurate to devices_list = ["GPU", "ANE"]
        # Actually the old devices() returned ["GPU", "ANE"] but power_usage() returned a single list [gpu+ane].
        # Let's map them properly to their respective devices in the dict.
        usage_dict = {
            "GPU": gpu_power,
            "ANE": ane_power
        }

        return PowerMeasurementData(
            timestamp=datetime.now(),
            component="gpu",
            power_usage_pr_device=usage_dict,
            pid=None
        )

    def parse_power(self, output: str, pattern: Pattern[str]) -> float:
        match = pattern.search(output)
        if match:
            power = float(match.group(1)) / 1000  # Convert mW to W (J/s)
            return power
        else:
            return 0.0
        
    def shutdown(self):
        pass
