import time
from src.config.config import (
    SessionConfig,
    SessionMode,
    RealPowerMeasurementConfig,
    IntensityMeasurementConfig,
    PredictionConfig,
    BudgetPolicy,
)
from src.config.config_manager import ResolvedConfig


def _generate_default_name() -> str:
    return f"run_{int(time.time())}"


def compile_session_config(
    resolved: ResolvedConfig,
    mode: SessionMode,
) -> SessionConfig:
    """
    Compiles a resolved user config into the internal SessionConfig.
    This is the boundary between frontend and backend.
    """
    defaults = resolved.defaults

    run_name = defaults.project_name or _generate_default_name()

    power_config = RealPowerMeasurementConfig(
        sample_interval=defaults.power_sampling_interval,
        components=defaults.components,
        pue=defaults.pue,
        devices_by_pids=[],
    )

    intensity_config = IntensityMeasurementConfig(
        sample_interval=defaults.intensity_sampling_interval,
        method=defaults.intensity_method.value,
        api_keys=resolved.api_keys or None,
        static_carbon_intensity_g_per_kwh=defaults.static_carbon_intensity_g_per_kwh,
        location=defaults.location,
    )

    prediction_config = PredictionConfig(
        enabled=defaults.predict_after is not None,
        unit_name=defaults.unit_name,
        total_units=defaults.total_units,
        predict_after_n_units=defaults.predict_after,
        forecast_interval_s=defaults.predict_interval,
    )

    budget_policy = None
    if defaults.max_energy_kwh is not None or defaults.max_emissions_g is not None:
        budget_policy = BudgetPolicy(
            max_energy_kwh=defaults.max_energy_kwh,
            max_emissions_g=defaults.max_emissions_g,
            action=defaults.action_on_breach.value,
            callback_on_trigger=defaults.on_breach_callback,
            evalaute_on_forecast=defaults.use_predicted_values,
        )

    return SessionConfig(
        mode=mode,
        run_name=run_name,
        log_dir=defaults.log_dir,
        ignore_errors=defaults.ignore_errors,
        provider_configs=[power_config, intensity_config],
        prediction_config=prediction_config,
        budget_policy=budget_policy,
    )
