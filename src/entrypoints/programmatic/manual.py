import time
from typing import Callable

from src.config.config import LogLevel, SessionMode, SessionConfig
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
        log_dir: str = "carbontracker_logs/",
        ignore_errors: bool = True,
        log_level: LogLevel = LogLevel.WARNING,
        session_stat_interval_s: float = 1.0,
        components: list[Component] | None = None,
        pue: float = 1.1,
        power_sampling_interval: float = 15.0,
        intensity_method: IntensityMethod = IntensityMethod.AUTO,
        intensity_sampling_interval: float = 900.0,
        location: Location | None = None,
        static_carbon_intensity_g_per_kwh: float | None = None,
        api_keys: dict[str, str] | None = None,
        predict_after_n_units: int | None = None,
        predict_interval_s: float | None = None,
        unit_name: str | None = None,
        max_energy_kwh: float | None = None,
        max_emissions_g: float | None = None,
        use_predicted_values: bool = False,
        action_on_breach: BreachAction = BreachAction.LOG,
        on_breach_callback: Callable | None = None,
    ) -> None:
        # Resolve dynamic defaults
        resolved_components = (
            components
            if components is not None
            else [Component.CPU, Component.GPU, Component.RAM]
        )
        resolved_run_name = (
            project_name if project_name is not None else _generate_default_name()
        )

        # TODO (dadyownes15): Integrate with project settings
        self._config = SessionConfig(
            # Identity
            mode=SessionMode.PYTHON_API,
            run_name=resolved_run_name,
            ignore_errors=ignore_errors,
            log_level=log_level,
            log_dir=log_dir,
            session_stat_interval_s=session_stat_interval_s,
            # Hardware & Power
            components=resolved_components,
            pue=pue,
            power_sampling_interval=power_sampling_interval,
            # Carbon Intensity
            intensity_method=intensity_method,
            intensity_sampling_interval=intensity_sampling_interval,
            location=location,
            static_carbon_intensity_g_per_kwh=static_carbon_intensity_g_per_kwh,
            api_keys=api_keys,
            # Prediction
            unit_name=unit_name,
            total_units=epochs,
            predict_after_n_units=predict_after_n_units,
            predict_interval_s=predict_interval_s,
            # Budget / Guardrails
            max_energy_kwh=max_energy_kwh,
            max_emissions_g=max_emissions_g,
            use_predicted_values=use_predicted_values,
            action_on_breach=action_on_breach,
            on_breach_callback=on_breach_callback,
            # Implicit / Not Exposed in this frontend
            command=None,
            devices_by_pids=[],
            total_duration=None,
            predict_after_n_secounds=None,
        )
        self._engine = CarbonTrackerEngine(self._config)

    def epoch_start(self):
        self._engine.epoch_start()

    def epoch_end(self):
        self._engine.epoch_end()

    def finish(self) -> FinishedSession:
        return self._engine.finish()
