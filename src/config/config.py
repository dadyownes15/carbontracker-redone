from enum import Enum
from typing import Callable, Dict, List, Literal, Union
from pydantic import BaseModel, Field

from src.core.types import Location, Component, IntensityMethod, BreachAction


class ProviderType(str, Enum):
    POWER = "power"
    INTENSITY = "intensity"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


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


class SessionConfig(BaseModel):
    # Session identity
    mode: SessionMode
    run_name: str
    command: list[str] | None = None
    ignore_errors: bool = True
    log_level: LogLevel = LogLevel.WARNING
    log_dir: str = "carbontracker_logs/"
    session_stat_interval_s: float = 1.0

    # Hardware & Power
    components: list[Component] = Field(default_factory=lambda: [Component.CPU, Component.GPU, Component.RAM])
    pue: float = 1.1
    power_sampling_interval: float = 15.0
    devices_by_pids: list[str] = Field(default_factory=list)

    # Carbon Intensity
    intensity_method: IntensityMethod = IntensityMethod.AUTO
    intensity_sampling_interval: float = 900.0
    location: Location | None = None
    static_carbon_intensity_g_per_kwh: float | None = None
    api_keys: dict[str, str] | None = None

    # Prediction
    predict_after: int = 2
    predict_interval: float = 60.0
    total_units: int | None = None
    unit_name: str = "epoch"

    # Budget / Guardrails
    max_energy_kwh: float | None = None
    max_emissions_g: float | None = None
    use_predicted_values: bool = False
    action_on_breach: BreachAction = BreachAction.LOG
    on_breach_callback: Callable | None = None

    model_config = {"arbitrary_types_allowed": True}
