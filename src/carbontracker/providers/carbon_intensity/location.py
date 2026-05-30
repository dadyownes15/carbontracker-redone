import json
import urllib.request
import urllib.error
from typing import Optional

from carbontracker.core.types import Location, GeoLocation, CloudRegion, ElectricityMapsGridZone, CountryCode
from carbontracker.providers.carbon_intensity.intensity_provider import (
    ResolvedLocation
)
from carbontracker.providers.carbon_intensity.country_defaults import CLOUD_REGION_TO_COUNTRY

def geolocate_by_ip() -> Optional[GeoLocation]:
    """
    Attempts to determine the user's geolocation using a public IP-based API.
    Returns GeoLocation if successful, None if it fails.
    This is best-effort and should fail silently to avoid breaking the execution.
    """
    try:
        # Using a free service without API key requirement
        with urllib.request.urlopen("http://ip-api.com/json/", timeout=2.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if data.get('status') == 'success':
                    return GeoLocation(
                        latitude=float(data.get('lat')),
                        longitude=float(data.get('lon'))
                    )
    except (urllib.error.URLError, json.JSONDecodeError, ValueError, TypeError):
        # Fail silently
        pass
    
    return None

def resolve_location(raw_location: Optional[str | Location], auto_detect: bool = True) -> ResolvedLocation:
    """
    Parses a raw location string into a concrete Location object, or returns the location if it's already a Location object.
    If raw_location is None and auto_detect is True, attempts IP geolocation.
    """
    if isinstance(raw_location, (GeoLocation, CloudRegion, ElectricityMapsGridZone, CountryCode)):
        return ResolvedLocation(
            location=raw_location,
            source="config",
            raw_input=str(raw_location)
        )
        
    if raw_location:
        raw = raw_location.strip()
        
        # 1. Check for Lat/Lon format (e.g. "55.67,12.56")
        if ',' in raw:
            parts = raw.split(',')
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    return ResolvedLocation(
                        location=GeoLocation(latitude=lat, longitude=lon),
                        source="config",
                        raw_input=raw_location
                    )
                except ValueError:
                    pass
        
        # 2. Check for Cloud Region format (e.g. "aws:eu-west-1")
        if ':' in raw:
            parts = raw.split(':', 1)
            if len(parts) == 2:
                provider = parts[0].strip().lower()
                region = parts[1].strip().lower()
                return ResolvedLocation(
                    location=CloudRegion(provider=provider, region=region),
                    source="config",
                    raw_input=raw_location
                )
                
        # 3. Check for Grid Zone (e.g. "DK-DK1" or "US-CAL-CISO")
        if '-' in raw:
            # Assuming anything with a hyphen that didn't match above is a grid zone
            return ResolvedLocation(
                location=ElectricityMapsGridZone(zone_id=raw.upper()),
                source="config",
                raw_input=raw_location
            )
            
        # 4. Assume Country Code (e.g. "DK")
        # Ensure it's a 2-letter code if possible, but allow others for now
        if len(raw) == 2:
            return ResolvedLocation(
                location=CountryCode(country_code=raw.upper()),
                source="config",
                raw_input=raw_location
            )
            
        # Default fallback if format is unrecognized but provided (treat as CountryCode or unknown)
        # We will wrap it in CountryCode and let the fallback chain deal with it.
        return ResolvedLocation(
            location=CountryCode(country_code=raw.upper()),
            source="config",
            raw_input=raw_location
        )

    # 5. No location provided, attempt IP Geolocation if allowed
    if auto_detect:
        geo = geolocate_by_ip()
        if geo:
            return ResolvedLocation(
                location=geo,
                source="geolocation",
                raw_input=None
            )

    # 6. Fallback: Unknown
    return ResolvedLocation(
        location=None,
        source="unknown",
        raw_input=None
    )

def location_to_country(loc: Location) -> Optional[str]:
    """Helper to try to extract a country code from any Location type."""
    if isinstance(loc, CountryCode):
        return loc.country_code
    elif isinstance(loc, ElectricityMapsGridZone):
        # Many grid zones start with the country code (e.g., DK-DK1 -> DK)
        if '-' in loc.zone_id:
            country = loc.zone_id.split('-')[0]
            if len(country) == 2:
                return country
    elif isinstance(loc, CloudRegion):
        key = f"{loc.provider}:{loc.region}"
        return CLOUD_REGION_TO_COUNTRY.get(key)
    # Note: GeoLocation reverse geocoding is omitted here for simplicity,
    # it would require an offline database or an API call.
    return None
