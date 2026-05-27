import time
from typing import Callable

from src.config.config import SessionMode, SessionConfig
from src.config.config_manager import resolve_overrides
from src.core.engine import CarbonTrackerEngine
from src.core.events import FinishedSession
from src.core.types import Component, Location, IntensityMethod, BreachAction


def _generate_default_name() -> str:
    return f"run_{int(time.time())}"


class CarbonTracker:
    """
    Manual epoch-based carbon tracking API.
    """

    def __init__(
        self,
        epochs: int,
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
        unit_name: str | None = None,
        max_energy_kwh: float | None = None,
        max_emissions_g: float | None = None,
        use_predicted_values: bool | None = None,
        action_on_breach: BreachAction | None = None,
        on_breach_callback: Callable | None = None,
    ):
        user_kwargs = {k: v for k, v in locals().items() if k != "self" and v is not None}
        overrides = resolve_overrides(**user_kwargs)
        
        # Mapping constructor args to SessionConfig fields where names differ slightly
        if "project_name" in overrides:
            overrides["run_name"] = overrides.pop("project_name")
        else:
            overrides["run_name"] = _generate_default_name()
            
        overrides["total_units"] = epochs

        self._config = SessionConfig(
            mode=SessionMode.PYTHON_API,
            **overrides
        )
        self._engine = CarbonTrackerEngine(self._config)

    def epoch_start(self):
        self._engine.epoch_start()

    def epoch_end(self):
        self._engine.epoch_end()

    def finish(self) -> FinishedSession:
        return self._engine.finish()
