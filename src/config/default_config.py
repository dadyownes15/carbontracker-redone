from typing import Callable
from pydantic import BaseModel, Field
from src.core.types import Component, BreachAction, IntensityMethod, Location


class TrackDefaults(BaseModel):
    """
    All user-facing configuration for a CarbonTracker session.
    Every field has a visible default. Pass an instance to CarbonTracker()
    or @track() to override any subset of values.
    """

    # ── Core Identification ──
    project_name: str | None = None  # None → auto-generated default name
    log_dir: str = "./carbontracker_logs/"
    ignore_errors: bool = True

    # ── Hardware & Providers ──
    components: list[Component] = Field(
        default=[Component.CPU, Component.GPU, Component.RAM]
    )
    pue: float = 1.1
    location: Location | None = None  # e.g., GridZone("DK-DK1")
    intensity_method: IntensityMethod = IntensityMethod.AUTO
    static_carbon_intensity_g_per_kwh: float | None = None

    # ── Sampling Intervals ──
    power_sampling_interval: float = 15.0  # seconds
    intensity_sampling_interval: float = 900.0  # seconds (15 min)

    # ── Prediction & Progress ──
    predict_after: int = 2  # units before first forecast
    predict_interval: float = 60.0  # re-predict every N seconds
    total_units: int | None = None
    unit_name: str = "epoch"

    # ── Budget / Guardrails ──
    max_energy_kwh: float | None = None
    max_emissions_g: float | None = None
    use_predicted_values: bool = False  # trigger guard on predicted vs actual
    action_on_breach: BreachAction = BreachAction.LOG
    on_breach_callback: Callable | None = None

    model_config = {"arbitrary_types_allowed": True}
