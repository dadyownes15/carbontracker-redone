from enum import Enum
from typing import Callable, Dict, List, Literal, Union
from pydantic import BaseModel, Field

from src.core.types import Location, Component


class ProjectConfig(BaseModel):
    name: str
    env_path: str
    log_dir: str


class SimulatedComponent(BaseModel):
    name: str
    power_draw_w: float


class ProviderType(str, Enum):
    POWER = "power"
    INTENSITY = "intensity"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ProviderConfig(BaseModel):
    provider_type: ProviderType
    sample_interval: float = 60.0


class RealPowerMeasurementConfig(ProviderConfig):
    provider_type: Literal[ProviderType.POWER] = ProviderType.POWER
    components: List[Component] = [Component.CPU, Component.RAM, Component.GPU]
    pue: float = 1.1
    devices_by_pids: List[str]


class SimulatedPowerMeasurementConfig(ProviderConfig):
    provider_type: Literal[ProviderType.POWER] = ProviderType.POWER
    simulated_components: List[SimulatedComponent] = Field(default_factory=list)


PowerMeasurementConfig = Union[
    RealPowerMeasurementConfig, SimulatedPowerMeasurementConfig
]


class IntensityMeasurementConfig(ProviderConfig):
    provider_type: Literal[ProviderType.INTENSITY] = ProviderType.INTENSITY
    method: Literal["electricityMaps", "static", "auto"] = "auto"
    location: Location | None = None
    auto_detect_location: bool = True
    static_carbon_intensity_g_per_kwh: float | None = None
    api_keys: Dict[str, str] | None = None


class PredictionConfig(BaseModel):
    enabled: bool = False
    unit_name: str = "epoch"
    total_units: int | None = None
    predict_after_n_units: int = 2
    forecast_interval_s: float = 60.0


class SessionMode(str, Enum):
    PYTHON_API = "python_api"
    PYTHON_DECORATOR = "python_decorator"
    SUBPROCESS = "subprocess"
    SLURM = "slurm"

    @property
    def is_python(self) -> bool:
        return self in (SessionMode.PYTHON_API, SessionMode.PYTHON_DECORATOR)

    @property
    def is_process(self) -> bool:
        return self in (SessionMode.SUBPROCESS, SessionMode.SLURM)


class ObserverConfig(BaseModel):
    prefix: str = "carbontracker"


class BudgetPolicy(BaseModel):
    max_intensity: float | None = None
    max_energy_kwh: float | None = None
    max_emissions_g: float | None = None
    max_duration_s: int | None = None
    callback_on_trigger: Callable | None = None
    action: Literal["log", "stop", "callback"] = "log"
    patience: int = 2
    evalaute_on_forecast: bool = False


class SessionConfig(BaseModel):
    mode: SessionMode
    run_name: str
    ignore_errors: bool = True
    project_config: ProjectConfig | None = None

    # Logging
    log_level: LogLevel = LogLevel.WARNING
    session_stat_interval_s: float = 1
    log_dir: str = "carbontracker_logs/"

    # Tracker configs
    provider_configs: List[ProviderConfig]
    observer_config: ObserverConfig = Field(default_factory=ObserverConfig)
    prediction_config: PredictionConfig = Field(default_factory=PredictionConfig)

    budget_policy: BudgetPolicy | None = None
