from typing import Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    name: str
    api_key_reference: str
    log_dir: str = "logs/"

class SimulatedComponent(BaseModel):
    # Defining this as a placeholder based on your tuple requirement
    name: str
    power_draw_w: float

class MeasurementConfig(BaseModel):
    components: List[Literal["cpu", "ram", "gpu"]] = ["cpu", "ram", "gpu"]
    sample_interval: float = 1.0
    pue: float = 1.1
    pids: List[int] = Field(default_factory=list)
    devices_by_pid: Dict[int, List[int]] = Field(default_factory=Dict)
    simulated_components: Tuple[SimulatedComponent, ...] = ()

class EmissionsConfig(BaseModel):
    method: Literal["electricityMaps", "static", "auto", "custom"] = "auto"
    location: Optional[str] = None
    sample_interval: float = 60.0
    provider_key_ref: Optional[str] = None
    static_carbon_intensity_g_per_kwh: Optional[float] = None


class PredictionConfig(BaseModel):
    enabled: bool = False
    predict_after: int = 2
    estimator: Literal["mean"] = "mean"
    confidence_intervals: bool = True
    validate_at_end: bool = False

class ObservationEventConfig(BaseModel):
    unit_name: str 
    total_units: Optional[int] = None
    autodetect: bool = True
    unit_marker: Optional[str] = None
    prediction_config: PredictionConfig 
    
class ObserverConfig(BaseModel):
    type: Literal["python", "process", "slurm-process"]
    events: Tuple[ObservationEventConfig,...]
    
class BudgetPolicy(BaseModel):
    max_intensity: Optional[float] = None
    max_energy_kwh: Optional[float] = None
    max_emissions_g: Optional[float] = None
    max_duration_s: Optional[int] = None
    action: Literal["raise", "warn", "stop", "checkpoint_and_stop"] = "warn"
    callbacks: List[str] = Field(default_factory=list)
    use_upper_bound_se: bool = True
    patience: int = 2

class SessionConfig(BaseModel):
    run_name: str
    project_config: ProjectConfig
    measurement_config: MeasurementConfig
    emissions_config: EmissionsConfig
    prediction_config: PredictionConfig
    budget_policy: BudgetPolicy
    progress_config: Optional[ProgressConfig] = None
    log_dir: Optional[str] = None
    flush_interval: int = 10
