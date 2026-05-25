import logging
from typing import List, Optional

from src.core.exceptions import ProviderConfigError, APIError
from src.core.config import IntensityMeasurementConfig
from src.data_provider.data_provider import DataProvider
from src.data_provider.data_provider_thread import DataProviderThread
from src.data_provider.carbon_intensity.intensity_provider import (
    IntensityMeasurementData, 
    IntensityResolution,
    ResolvedLocation
)
from src.core.resolution import ResolutionStep
from src.data_provider.carbon_intensity.location import resolve_location, location_to_country
from src.data_provider.carbon_intensity.providers.electricity_maps import ElectricityMapsProvider
from src.data_provider.carbon_intensity.providers.static_provider import (
    StaticProvider,
    StaticCountryProvider,
    GlobalAverageProvider
)

logger = logging.getLogger("carbontracker.intensity_factory")

import queue
from threading import Event
from src.core.events import TrackerEvent

def create_intensity_thread(
    config: IntensityMeasurementConfig,
    aggregation_queue: "queue.Queue[TrackerEvent]",
    notify_event: Event
) -> DataProviderThread[IntensityMeasurementData]:
    """
    Creates a ProviderThread encapsulating the resolved intensity provider.
    This also handles printing the resolution log to the user.
    """
    resolution = resolve_intensity_provider(config)
    print_resolution(resolution)
    
    return DataProviderThread(
        sample_interval=config.sample_interval,
        providers=[resolution.provider],
        aggregation_queue=aggregation_queue,
        notify_event=notify_event
    )


def resolve_intensity_provider(config: IntensityMeasurementConfig) -> IntensityResolution:
    """
    Implements the deterministic fallback chain for intensity providers.
    """
    steps: List[ResolutionStep] = []
    
    # 1. Resolve Location
    resolved_loc = resolve_location(config.location, config.auto_detect_location)
    
    if resolved_loc.source == "config":
        steps.append(ResolutionStep(
            action="location_config",
            detail=f"Using configured location: {resolved_loc.raw_input}",
            level="info"
        ))
    elif resolved_loc.source == "geolocation":
        loc_data = resolved_loc.location.data
        steps.append(ResolutionStep(
            action="location_geolocation",
            detail=f"Location detected via IP geolocation: {loc_data.latitude}, {loc_data.longitude}",
            level="info"
        ))
    else:
        steps.append(ResolutionStep(
            action="location_unknown",
            detail="No location specified and geolocation failed or disabled.",
            level="warning"
        ))
        
    # 2. Select Provider based on Method
    method = config.method
    
    if method == "static":
        if config.static_carbon_intensity_g_per_kwh is not None:
            provider = StaticProvider(resolved_loc, config.static_carbon_intensity_g_per_kwh)
            steps.append(ResolutionStep(
                action="provider_static_override",
                detail=f"Using static carbon intensity (user-defined: {config.static_carbon_intensity_g_per_kwh} g CO₂eq/kWh)",
                level="success"
            ))
            return IntensityResolution(provider, resolved_loc, steps)
        else:
            # Try country fallback
            country = location_to_country(resolved_loc.location) if resolved_loc.location else None
            if country:
                provider = StaticCountryProvider(resolved_loc, country)
                steps.append(ResolutionStep(
                    action="provider_static_country",
                    detail=f"Using static country average ({country})",
                    level="success"
                ))
            else:
                provider = GlobalAverageProvider(resolved_loc)
                steps.append(ResolutionStep(
                    action="provider_global_average",
                    detail="Using global average (475 g CO₂eq/kWh)",
                    level="warning"
                ))
            return IntensityResolution(provider, resolved_loc, steps)

    elif method == "electricityMaps":
        em_key = config.api_keys.get("electricityMaps") if config.api_keys else None
        if not em_key:
            raise ProviderConfigError("electricityMaps method requires an API key in config.api_keys['electricityMaps']")
            
        provider = ElectricityMapsProvider(resolved_loc, em_key)
        steps.append(ResolutionStep(
            action="provider_electricitymaps",
            detail=f"Using: {provider.name}",
            level="success"
        ))
        return IntensityResolution(provider, resolved_loc, steps)

    elif method == "auto":
        # Check keys
        em_key = config.api_keys.get("electricityMaps") if config.api_keys else None
        if em_key and resolved_loc.source != "unknown":
            try:
                provider = ElectricityMapsProvider(resolved_loc, em_key)
                steps.append(ResolutionStep(
                    action="api_key_found",
                    detail="Electricity Maps API key found",
                    level="info"
                ))
                steps.append(ResolutionStep(
                    action="provider_electricitymaps",
                    detail=f"Using: {provider.name}",
                    level="success"
                ))
                return IntensityResolution(provider, resolved_loc, steps)
            except ProviderConfigError as e:
                # E.g. couldn't build query params from location
                steps.append(ResolutionStep(
                    action="api_provider_failed",
                    detail=f"Electricity Maps API configured but location format unsupported: {e}",
                    level="warning"
                ))
                logger.warning(f"Electricity Maps API configured but location format unsupported: {e}")
            except APIError as e:
                steps.append(ResolutionStep(
                    action="api_provider_failed",
                    detail=f"Electricity Maps API failed: {e}",
                    level="warning"
                ))
                logger.warning(f"Electricity Maps API failed: {e}")
        
        # Auto fallback -> country average -> global average
        if not em_key:
            steps.append(ResolutionStep(
                action="no_api_key",
                detail="No API key configured for real-time data.",
                level="warning"
            ))
            
        country = location_to_country(resolved_loc.location) if resolved_loc.location else None
        if country:
            provider = StaticCountryProvider(resolved_loc, country)
            steps.append(ResolutionStep(
                action="provider_static_country",
                detail=f"Using static country average ({country})",
                level="success"
            ))
        else:
            provider = GlobalAverageProvider(resolved_loc)
            steps.append(ResolutionStep(
                action="provider_global_average",
                detail="Using global average (475 g CO₂eq/kWh)",
                level="warning"
            ))
            
        return IntensityResolution(provider, resolved_loc, steps)
        
    else:
        raise ValueError(f"Unrecognized intensity method: {method}")

def print_resolution(resolution):    
    for step in resolution.steps:
        if step.level == "success":
            logger.info(f"✓ {step.detail}")
        elif step.level == "warning":
            logger.warning(f"⚠ {step.detail}")
        else:
            logger.info(f"ℹ {step.detail}")