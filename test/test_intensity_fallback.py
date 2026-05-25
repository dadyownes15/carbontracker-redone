import pytest
from src.core.config import IntensityMeasurementConfig
from src.data_provider.carbon_intensity.location import resolve_location, location_to_country
from src.data_provider.carbon_intensity.intensity_provider import (
    CountryCode, GridZone, CloudRegion, GeoLocation
)
from src.data_provider.carbon_intensity.factory import resolve_intensity_provider
from src.data_provider.carbon_intensity.providers.electricity_maps import ElectricityMapsProvider
from src.data_provider.carbon_intensity.providers.static_provider import (
    StaticCountryProvider, GlobalAverageProvider, StaticProvider
)

def test_resolve_location_parsing():
    # Country Code
    res = resolve_location("DK", auto_detect=False)
    assert res.source == "config"
    assert isinstance(res.location.data, CountryCode)
    assert res.location.data.country_code == "DK"
    
    # Grid Zone
    res = resolve_location("DK-DK1", auto_detect=False)
    assert isinstance(res.location.data, GridZone)
    assert res.location.data.zone_id == "DK-DK1"
    
    # Cloud Region
    res = resolve_location("aws:eu-west-1", auto_detect=False)
    assert isinstance(res.location.data, CloudRegion)
    assert res.location.data.provider == "aws"
    assert res.location.data.region == "eu-west-1"
    
    # Lat/Lon
    res = resolve_location("55.67, 12.56", auto_detect=False)
    assert isinstance(res.location.data, GeoLocation)
    assert res.location.data.latitude == 55.67
    assert res.location.data.longitude == 12.56

def test_location_to_country():
    # Cloud region fallback
    res = resolve_location("aws:eu-west-1", auto_detect=False)
    assert location_to_country(res.location) == "IE"
    
    # Grid zone fallback
    res = resolve_location("DK-DK1", auto_detect=False)
    assert location_to_country(res.location) == "DK"

def test_factory_electricity_maps():
    config = IntensityMeasurementConfig(
        method="electricityMaps",
        location="DK",
        api_keys={"electricityMaps": "test-key"}
    )
    resolution = resolve_intensity_provider(config)
    assert isinstance(resolution.provider, ElectricityMapsProvider)
    assert resolution.provider.api_key == "test-key"

def test_factory_static_override():
    config = IntensityMeasurementConfig(
        method="static",
        static_carbon_intensity_g_per_kwh=123.4
    )
    resolution = resolve_intensity_provider(config)
    assert isinstance(resolution.provider, StaticProvider)
    assert not isinstance(resolution.provider, StaticCountryProvider)
    assert resolution.provider.intensity_value == 123.4

def test_factory_auto_fallback_to_country():
    # No API key, but location provided (auto method)
    config = IntensityMeasurementConfig(
        method="auto",
        location="DK",
        api_keys=None
    )
    resolution = resolve_intensity_provider(config)
    assert isinstance(resolution.provider, StaticCountryProvider)
    assert resolution.provider.intensity_value == 166.0 # DK default

def test_factory_auto_fallback_to_global():
    # No API key, no location, auto_detect false
    config = IntensityMeasurementConfig(
        method="auto",
        location=None,
        auto_detect_location=False
    )
    resolution = resolve_intensity_provider(config)
    assert isinstance(resolution.provider, GlobalAverageProvider)
    assert resolution.provider.intensity_value == 475.0
