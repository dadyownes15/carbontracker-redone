from pathlib import Path
from typing import Any

from carbontracker.config.config_manager import (
    GlobalConfig,
    _write_toml,
    get_global_config_file,
    get_local_config_file,
    save_global_config,
)


def default_project_config(project_dir: Path | None = None) -> dict[str, Any]:
    root = project_dir if project_dir is not None else Path.cwd()
    return {
        "project_name": root.name,
        "log_dir": "carbontracker_logs/",
        "components": ["cpu", "gpu", "ram"],
        "power_sampling_interval": 15.0,
        "intensity_sampling_interval": 900.0,
        "intensity_method": "auto",
    }


def init_project_config(
    *,
    project_name: str | None = None,
    log_dir: str | None = None,
    components: list[str] | tuple[str, ...] | None = None,
    power_sampling_interval: float | None = None,
    intensity_sampling_interval: float | None = None,
    intensity_method: str | None = None,
    static_carbon_intensity_g_per_kwh: float | None = None,
    forecast_provider_name: str | None = None,
) -> Path:
    config = default_project_config()
    explicit_values: dict[str, Any] = {
        "project_name": project_name,
        "log_dir": log_dir,
        "components": list(components) if components is not None else None,
        "power_sampling_interval": power_sampling_interval,
        "intensity_sampling_interval": intensity_sampling_interval,
        "intensity_method": intensity_method,
        "static_carbon_intensity_g_per_kwh": static_carbon_intensity_g_per_kwh,
        "forecast_provider_name": forecast_provider_name,
    }
    config.update(
        {key: value for key, value in explicit_values.items() if value is not None}
    )

    path = get_local_config_file()
    _write_toml(path, config)
    return path


def init_global_config(
    *,
    api_keys: dict[str, str] | None = None,
    default_location: Any | None = None,
    default_pue: float | None = None,
) -> Path:
    config = GlobalConfig(
        api_keys=api_keys or {},
        default_location=default_location,
        default_pue=default_pue,
    )
    save_global_config(config)
    return get_global_config_file()
