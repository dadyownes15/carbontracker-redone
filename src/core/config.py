from enum import Enum
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    name: str
    api_key_reference: str
    log_dir: str = "logs/"


class SimulatedComponent(BaseModel):
    name: str
    power_draw_w: float


class ProviderType(str, Enum):
    POWER = "power"
    INTENSITY = "intensity"


class ProviderConfig(BaseModel):
    provider_type: ProviderType
    sample_interval: float = 60.0

class RealPowerMeasurementConfig(ProviderConfig):
    provider_type: Literal[ProviderType.POWER] = ProviderType.POWER
    components: List[Literal["cpu", "ram", "gpu"]] = ["cpu", "ram", "gpu"]
    pue: float = 1.1
    devices_by_pids: List[str]

class SimulatedPowerMeasurementConfig(ProviderConfig):
    provider_type: Literal[ProviderType.POWER] = ProviderType.POWER
    sample_interval: float = 0.0
    simulated_components: List[SimulatedComponent] = Field(default_factory=list)

PowerMeasurementConfig = Union[RealPowerMeasurementConfig, SimulatedPowerMeasurementConfig]

class IntensityMeasurementConfig(ProviderConfig):
    provider_type: Literal[ProviderType.INTENSITY] = ProviderType.INTENSITY
    method: Literal["electricityMaps", "static", "auto"] = "auto"
    location: Optional[str] = None
    auto_detect_location: bool = True
    provider_key_ref: Optional[str] = None
    static_carbon_intensity_g_per_kwh: Optional[float] = None
    api_keys: Optional[Dict[str, str]] = None


class PredictionConfig(BaseModel):
    enabled: bool = False
    unit_name: str = "epoch"
    total_units: Optional[int] = None
    predict_after: int = 2
    estimator: Literal["mean"] = "mean"
    confidence_intervals: bool = True
    validate_at_end: bool = False


class ObserverConfig(BaseModel):
    type: Literal["python-manual","python-decorator", "process", "slurm-process"]
    prefix: str = "carbontracker" 


class BudgetPolicy(BaseModel):
    max_intensity: Optional[float] = None
    max_energy_kwh: Optional[float] = None
    max_emissions_g: Optional[float] = None
    max_duration_s: Optional[int] = None
    action: Literal["raise", "warn", "stop", "checkpoint_and_stop"] = "warn"
    use_upper_bound_se: bool = True
    patience: int = 2


class SessionConfig(BaseModel):
    run_name: str
    log_dir: str
    flush_interval: int = 10
    log_level: int = 20  # logging.INFO default
    project_config: Optional[ProjectConfig] = None

    # Tracker configs
    provider_configs: List[Union[PowerMeasurementConfig, IntensityMeasurementConfig]]
    observer_config: ObserverConfig
    prediction_config: PredictionConfig = Field(default_factory=PredictionConfig)

    # Separated budget policies for actuals vs. forecasts
    budget_policy: Optional[BudgetPolicy] = None
    forecast_budget_policy: Optional[BudgetPolicy] = None

    @classmethod
    def from_legacy_args(
        cls,
        epochs: int,
        epochs_before_pred: int = 1,
        monitor_epochs: int = -1,
        update_interval: Union[int, float] = 1,
        interpretable: bool = True,
        stop_and_confirm: bool = False,
        ignore_errors: bool = False,
        components: str = "all",
        devices_by_pid: bool = False,
        log_dir: Optional[str] = None,
        log_file_prefix: str = "",
        verbose: int = 1,
        decimal_precision: int = 12,
        api_keys: Optional[Dict[str, str]] = None,
        sim_cpu: Optional[str] = None,
        sim_cpu_tdp: Optional[float] = None,
        sim_cpu_util: Optional[float] = None,
        sim_gpu: Optional[str] = None,
        sim_gpu_watts: Optional[float] = None,
        sim_gpu_util: Optional[float] = None,
        **kwargs
    ) -> "SessionConfig":

        # 1. Parse Components
        parsed_components = []
        if components == "all":
            parsed_components = ["cpu", "ram", "gpu"]
        else:
            comp_list = [c.strip().lower() for c in components.split(",")]
            if "cpu" in comp_list: parsed_components.append("cpu")
            if "gpu" in comp_list: parsed_components.append("gpu")
            if "ram" in comp_list: parsed_components.append("ram")

        sim_comps = []
        if sim_cpu and sim_cpu_tdp is not None:
            sim_comps.append(SimulatedComponent(name=sim_cpu, power_draw_w=sim_cpu_tdp))
        if sim_gpu and sim_gpu_watts is not None:
            sim_comps.append(SimulatedComponent(name=sim_gpu, power_draw_w=sim_gpu_watts))

        # 2. Build Providers
        power_config = RealPowerMeasurementConfig(
            sample_interval=float(update_interval),
            components=parsed_components,
            devices_by_pids=[]
        )
        # TODO: Handle simulated components properly in the legacy bridge if needed

        intensity_config = IntensityMeasurementConfig(
            sample_interval=900.0,
            api_keys=api_keys,
            method="auto" if api_keys else "static"
        )

        # 3. Build Prediction Config
        pred_enabled = epochs_before_pred > 0
        prediction_config = PredictionConfig(
            enabled=pred_enabled,
            unit_name="epoch",
            total_units=epochs,  # Total units now lives entirely in prediction context
            predict_after=epochs_before_pred if pred_enabled else 2
        )

        # 4. Observer Config (Incredibly simple now)
        observer_config = ObserverConfig(type="python-manual")

        # 5. Budget Policies
        forecast_budget_policy = None
        if stop_and_confirm:
            forecast_budget_policy = BudgetPolicy(action="checkpoint_and_stop")

        resolved_log_dir = log_dir if log_dir else "logs/"
        run_name = log_file_prefix if log_file_prefix else "legacy_run"

        # Map legacy verbose (0, 1, 2) to logging levels
        if verbose == 0:
            log_level = 30 # logging.WARNING
        elif verbose >= 2:
            log_level = 10 # logging.DEBUG
        else:
            log_level = 20 # logging.INFO

        return cls(
            run_name=run_name,
            log_dir=resolved_log_dir,
            project_config=ProjectConfig(
                name=run_name,
                api_key_reference="legacy_env",
                log_dir=resolved_log_dir
            ),
            provider_configs=[power_config, intensity_config],
            observer_config=observer_config,
            prediction_config=prediction_config,
            budget_policy=None,
            forecast_budget_policy=forecast_budget_policy,
            log_level=log_level
        )
