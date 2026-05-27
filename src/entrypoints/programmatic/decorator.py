import functools
import time
from typing import Callable

from src.config.config import SessionMode, SessionConfig
from src.config.config_manager import resolve_overrides
from src.core.engine import CarbonTrackerEngine
from src.core.types import Component, Location, IntensityMethod, BreachAction


def _generate_default_name() -> str:
    return f"run_{int(time.time())}"


def track(
    *,
    project_name: str | None = None,
    log_dir: str | None = None,
    ignore_errors: bool | None = None,
    components: list[Component] | None = None,
    pue: float | None = None,
    location: Location | None = None,
    intensity_method: IntensityMethod | None = None,
    static_carbon_intensity_g_per_kwh: float | None = None,
    power_sampling_interval: float | None = None,
    intensity_sampling_interval: float | None = None,
    predict_after: int | None = None,
    predict_interval: float | None = None,
    total_units: int | None = None,
    unit_name: str | None = None,
    max_energy_kwh: float | None = None,
    max_emissions_g: float | None = None,
    use_predicted_values: bool | None = None,
    action_on_breach: BreachAction | None = None,
    on_breach_callback: Callable | None = None,
):
    """
    Decorator to track the carbon footprint of a function.
    """
    user_kwargs = {k: v for k, v in locals().items() if v is not None}
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            overrides = resolve_overrides(**user_kwargs)
            
            if "project_name" in overrides:
                overrides["run_name"] = overrides.pop("project_name")
            else:
                overrides["run_name"] = _generate_default_name()

            config = SessionConfig(
                mode=SessionMode.PYTHON_DECORATOR,
                **overrides
            )
            engine = CarbonTrackerEngine(config)
            try:
                return func(*args, **kwargs)
            finally:
                engine.finish()
        return wrapper
    return decorator
