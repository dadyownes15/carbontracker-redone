import os
import sys
from unittest.mock import MagicMock
# Mock src.core.engine to bypass import errors caused by src/__init__.py
sys.modules['src.core.engine'] = MagicMock()
from carbontracker.core.types import CountryCode
from carbontracker.providers.carbon_intensity.intensity_provider import ResolvedLocation
from carbontracker.providers.carbon_intensity_forecast.providers.electricity_maps import ElectricityMapsForecastProvider

def main():
    api_key = None
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("electricity_maps="):
                    api_key = line.split("=", 1)[1].strip().strip('"\'')
                    
    if not api_key:
        print("electricity_maps key not found in .env. Please set it to test.")
        return

    # Create a resolved location for Denmark
    loc = ResolvedLocation(
        location=CountryCode(country_code="DK-DK1"),
        source="test",
        raw_input=CountryCode(country_code="DK-DK1")
    )
    
    print("Initializing ElectricityMapsForecastProvider...")
    provider = ElectricityMapsForecastProvider(location=loc, api_key=api_key)
    
    print(f"Provider name: {provider.name}")
    print("Fetching forecast...")
    try:
        data = provider.fetch()
        print(f"Successfully fetched forecast!")
        print(f"Timestamp of fetch: {data.timestamp}")
        print(f"Location: {data.location}")
        print(f"Number of forecast points: {len(data.forecasts)}")
        
        if data.forecasts:
            print("\nFirst 3 forecast points:")
            for p in data.forecasts[:3]:
                print(f"  Time: {p.timestamp}, Intensity: {p.carbon_intensity} gCO2eq/kWh")
                
            print("\nLast forecast point:")
            p = data.forecasts[-1]
            print(f"  Time: {p.timestamp}, Intensity: {p.carbon_intensity} gCO2eq/kWh")
    except Exception as e:
        print(f"Failed to fetch forecast: {e}")

if __name__ == "__main__":
    main()
