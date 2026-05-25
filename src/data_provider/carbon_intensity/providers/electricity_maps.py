import json
import urllib.request
import urllib.error
from datetime import datetime
from src.data_provider.data_provider import DataProvider
from src.data_provider.carbon_intensity.intensity_provider import (
    IntensityMeasurementData, 
    ResolvedLocation,
    GridZone,
    GeoLocation,
    CountryCode
)
from src.core.exceptions import ProviderConfigError, APIError

class ElectricityMapsProvider(DataProvider[IntensityMeasurementData]):
    """
    Real-time carbon intensity provider using the Electricity Maps API.
    """
    BASE_URL = "https://api.electricitymap.org/v3/carbon-intensity/latest"

    def __init__(self, location: ResolvedLocation, api_key: str):
        self.location = location
        self.api_key = api_key
        
        # Build query parameters based on location type
        self.query_params = {}
        if location.location:
            data = location.location.data
            if isinstance(data, GridZone):
                self.query_params['zone'] = data.zone_id
            elif isinstance(data, GeoLocation):
                self.query_params['lat'] = str(data.latitude)
                self.query_params['lon'] = str(data.longitude)
            elif isinstance(data, CountryCode):
                # EM supports zones which are often country codes
                self.query_params['zone'] = data.country_code
                
        if not self.query_params:
            raise ProviderConfigError("Electricity Maps API requires a valid zone or lat/lon location.")

    @property
    def name(self) -> str:
        if 'zone' in self.query_params:
            return f"Electricity Maps API (zone: {self.query_params['zone']})"
        return "Electricity Maps API"

    def fetch(self) -> IntensityMeasurementData:
        url = self.BASE_URL
        if self.query_params:
            import urllib.parse
            url += "?" + urllib.parse.urlencode(self.query_params)
            
        req = urllib.request.Request(url, headers={"auth-token": self.api_key})
        try:
            with urllib.request.urlopen(req, timeout=10.0) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode('utf-8'))
                    intensity = float(payload.get('carbonIntensity', 0.0))
                    
                    return IntensityMeasurementData(
                        timestamp=datetime.now(),
                        location=self.location.location,
                        intensity=intensity,
                        is_prediction=False
                    )
                else:
                    raise APIError(f"Electricity Maps API returned status {response.status}")
        except Exception as e:
            # Fallback or raise error depending on design; for now raise
            raise APIError(f"Failed to fetch from Electricity Maps: {e}")

    def shutdown(self) -> None:
        pass
