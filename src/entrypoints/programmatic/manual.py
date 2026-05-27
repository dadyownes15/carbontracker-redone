from typing import Callable

from src.config.default_config import TrackDefaults
from src.config.config_manager import resolve_config
from src.config.compiler import compile_session_config
from src.config.config import SessionMode
from src.core.engine import CarbonTrackerEngine
from src.core.events import FinishedSession
from src.core.types import Component, BreachAction, IntensityMethod, Location


class CarbonTracker:
    """
    Manual epoch-based carbon tracking API.

    Args:
        epochs: Total number of epochs to track.
        config: A TrackDefaults instance with pre-set values. Any kwarg
                overrides fields on this config.

    Keyword overrides (see TrackDefaults for full list and defaults):
        project_name:                   str | None  (default: None → auto)
        log_dir:                        str         (default: "./carbontracker_logs/")
        ignore_errors:                  bool        (default: True)
        components:                     list[Component] (default: [CPU, GPU, RAM])
        pue:                            float       (default: 1.1)
        location:                       Location | None (default: None → auto-detect)
        intensity_method:               IntensityMethod (default: AUTO)
        static_carbon_intensity_g_per_kwh: float | None (default: None)
        power_sampling_interval:        float       (default: 15.0s)
        intensity_sampling_interval:    float       (default: 900.0s)
        predict_after:                  int         (default: 2 units)
        predict_interval:               float       (default: 60.0s)
        total_units:                    int | None  (default: None)
        unit_name:                      str         (default: "epoch")
        max_energy_kwh:                 float | None (default: None)
        max_emissions_g:                float | None (default: None)
        use_predicted_values:           bool        (default: False)
        action_on_breach:               BreachAction (default: LOG)
        on_breach_callback:             Callable | None (default: None)
    """

    def __init__(self, epochs: int, config: TrackDefaults | None = None, **overrides):
        if config is not None:
            effective = config.model_copy(update=overrides)
        else:
            effective = TrackDefaults(**overrides)

        # epochs maps to total_units + unit_name for the prediction engine
        effective.total_units = epochs
        effective.unit_name = "epoch"

        resolved = resolve_config(effective)
        session_config = compile_session_config(resolved, mode=SessionMode.PYTHON_API)
        self._engine = CarbonTrackerEngine(session_config)

    def epoch_start(self):
        self._engine.epoch_start()

    def epoch_end(self):
        self._engine.epoch_end()

    def finish(self) -> FinishedSession:
        return self._engine.finish()
