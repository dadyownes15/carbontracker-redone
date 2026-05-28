import logging
import queue
from threading import Event

from src.core.events import TrackerEvent
from src.core.exceptions import ProviderConfigError, APIError
from src.core.resolution import ResolutionStep, print_resolution_steps
from src.providers.carbon_intensity.intensity_provider import ResolvedLocation
from src.providers.carbon_intensity_forecast.forecast_provider import (
    ForecastResolution,
    IntensityForecastData,
)
from src.providers.carbon_intensity_forecast.providers.electricity_maps import (
    ElectricityMapsForecastProvider,
)
from src.providers.carbon_intensity_forecast.providers.static_provider import (
    StaticForecastProvider,
)
from src.providers.data_provider_thread import DataProviderThread

logger = logging.getLogger("carbontracker.forecast_factory")


def resolve_forecast_provider(
    location: ResolvedLocation,
    current_intensity: float,
    provider_type: str,
    api_key: str | None = None,
    forecast_length_hours: int = 24,
    forecast_interval_hours: int = 1,
) -> ForecastResolution:
    """
    Implements the deterministic fallback chain for forecast providers.
    Requires current_intensity from the real-time provider for the static fallback.
    """
    steps: list[ResolutionStep] = []

    # 1. Select Provider based on provider_type
    if provider_type == "electricityMaps":
        if api_key and location.source != "unknown":
            try:
                provider = ElectricityMapsForecastProvider(location, api_key)
                steps.append(
                    ResolutionStep(
                        action="api_key_found",
                        detail="Electricity Maps API key found for forecast",
                        level="info",
                    )
                )
                steps.append(
                    ResolutionStep(
                        action="provider_electricitymaps_forecast",
                        detail=f"Using: {provider.name}",
                        level="success",
                    )
                )
                return ForecastResolution(provider, location, steps)
            except ProviderConfigError as e:
                steps.append(
                    ResolutionStep(
                        action="api_provider_failed",
                        detail=f"Electricity Maps Forecast API configured but location format unsupported: {e}",
                        level="warning",
                    )
                )
                logger.warning(
                    f"Electricity Maps Forecast API configured but location format unsupported: {e}"
                )
            except APIError as e:
                steps.append(
                    ResolutionStep(
                        action="api_provider_failed",
                        detail=f"Electricity Maps Forecast API failed: {e}",
                        level="warning",
                    )
                )
                logger.warning(f"Electricity Maps Forecast API failed: {e}")
        else:
            if not api_key:
                steps.append(
                    ResolutionStep(
                        action="no_api_key",
                        detail="No API key configured for real-time forecast data.",
                        level="warning",
                    )
                )
            if location.source == "unknown":
                steps.append(
                    ResolutionStep(
                        action="location_unknown",
                        detail="Location is unknown, cannot use Electricity Maps API.",
                        level="warning",
                    )
                )

    elif provider_type != "static":
        steps.append(
            ResolutionStep(
                action="unknown_provider_type",
                detail=f"Unrecognized forecast provider type: {provider_type}. Falling back to static.",
                level="warning",
            )
        )

    # 2. Fallback to Static Forecast Provider
    provider = StaticForecastProvider(
        location=location,
        current_intensity=current_intensity,
        forecast_length_hours=forecast_length_hours,
        forecast_interval_hours=forecast_interval_hours,
    )
    steps.append(
        ResolutionStep(
            action="provider_static_forecast",
            detail=f"Using naive static forecast provider (projecting {current_intensity} g CO₂eq/kWh for {forecast_length_hours} hours)",
            level="success",
        )
    )
    return ForecastResolution(provider, location, steps)


def create_intensity_forecast_thread(
    location: ResolvedLocation,
    current_intensity: float,
    aggregation_queue: queue.Queue[TrackerEvent],
    provider_type: str,
    api_key: str | None = None,
    forecast_length_hours: int = 24,
    forecast_interval_hours: int = 1,
    sample_interval: int = 3600,
) -> DataProviderThread[IntensityForecastData]:
    resolution: ForecastResolution = resolve_forecast_provider(
        location=location,
        current_intensity=current_intensity,
        provider_type=provider_type,
        api_key=api_key,
        forecast_length_hours=forecast_length_hours,
        forecast_interval_hours=forecast_interval_hours,
    )

    print_resolution_steps(resolution.steps, logger)

    return DataProviderThread(
        sample_interval=sample_interval,
        providers=[resolution.provider],
        aggregation_queue=aggregation_queue,  # Update based on how it's actually integrated
        notify_event=Event(),  # set an forget
        initial_work=True,
    )
