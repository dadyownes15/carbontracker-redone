import logging
import numpy as np
from typing import List, Tuple
from datetime import datetime

from src.core.stats import SpanStats
from src.providers.power.power_provider import PowerMeasurementData
from src.providers.carbon_intensity.intensity_provider import IntensityMeasurementData

logger = logging.getLogger("carbontracker.integration")

def get_intensity_at(t: datetime, intensities: List[Tuple[datetime, float]]) -> float:
    """
    Finds the active carbon intensity at a specific moment in time.
    Uses Last-Observation-Carried-Forward (the most recent reading prior to or exactly at t).
    """
    if not intensities:
        return 0.0
        
    intensity = intensities[0][1]
    for i_time, i_val in intensities:
        if i_time <= t:
            intensity = i_val
        else:
            break 
            
    return intensity

def calculate_device_energy_and_emissions(
    device_name: str,
    power_measurements: List[Tuple[datetime, float]], 
    intensity_measurements: List[Tuple[datetime, float]],
    t_start: datetime, 
    t_stop: datetime
) -> Tuple[float, float, float, float, float]:
    """
    Calculates total energy, power stats, and strictly-weighted emissions for a single device.
    The integration is split into three segments to accurately model step-function workloads:
    
    Power (W)
      ^
      |                  (t_2,P_2)           (t_3, P_3)    (t_stop,P_3)
      |                     |                     |            | 
      |                     o---------------------o------------o                     
      |                    /|                     |  Segment C |  
      |                   / |                     | Rectangle  | 
      |                  /  |                     |            |
      |     (t_1, P_1)  /   |      Segment B      |            |
      |         o      /    |     Trapezoids      |            |
      |         |     /     |                     |            |
      |         |    /      |                     |            |
      |         |   /       |                     |            |
    --|---------|-----------|---------------------|------------|-----> Time
    t_start    t_1         t_2                   t_3         t_stop

    Returns:
        Tuple of (total_energy_joules, avg_watt, min_watt, max_watt, total_emissions_g)
    """
    if not power_measurements:
        return 0.0, 0.0, 0.0, 0.0, 0.0
        
    duration_s = (t_stop - t_start).total_seconds()
    if duration_s <= 0:
        logger.warning(f"[{device_name}] Invalid epoch duration: {duration_s}s. Returning 0.")
        return 0.0, 0.0, 0.0, 0.0, 0.0

    # Ensure we only use measurements strictly inside the epoch
    valid_m = [m for m in power_measurements if t_start <= m[0] <= t_stop]
    if not valid_m:
        logger.warning(f"[{device_name}] No valid measurements found between {t_start} and {t_stop}.")
        return 0.0, 0.0, 0.0, 0.0, 0.0

    powers = np.array([p for _, p in valid_m])
    times_s = np.array([(t - t_start).total_seconds() for t, _ in valid_m])
    
    # Data Validation
    if np.any(powers < 0):
        logger.warning(f"[{device_name}] Negative power draw detected. This may indicate a hardware sensor error.")
    
    min_watt = float(np.min(powers))
    max_watt = float(np.max(powers))

    total_energy_joules = 0.0
    total_emissions_g = 0.0
    JOULES_TO_KWH = 3600000.0

    # Segment A: The Ramp Up
    segment_a_duration = times_s[0]
    if segment_a_duration > 10.0:
        logger.warning(f"[{device_name}] Large gap ({segment_a_duration:.1f}s) between epoch start and first measurement.")
        
    energy_a = powers[0] * segment_a_duration
    total_energy_joules += energy_a
    total_emissions_g += (energy_a / JOULES_TO_KWH) * get_intensity_at(t_start, intensity_measurements)
    
    # Segment B: Interior trapezoids using Numpy Vectorization
    if len(valid_m) > 1:
        dt = np.diff(times_s)
        
        if np.any(dt > 30.0):
            logger.warning(f"[{device_name}] Unusually large time gap (>30s) between consecutive polling measurements.")
            
        avg_p = (powers[:-1] + powers[1:]) / 2.0
        energy_b_segments = avg_p * dt
        
        # Get intensities for the start of each trapezoid
        intensities_b = np.array([get_intensity_at(valid_m[i][0], intensity_measurements) for i in range(len(valid_m)-1)])
        
        total_energy_joules += np.sum(energy_b_segments)
        total_emissions_g += np.sum(energy_b_segments * intensities_b) / JOULES_TO_KWH
        
    # Segment C: The Block-Wave Tail (LOCF)
    segment_c_duration = duration_s - times_s[-1]
    energy_c = powers[-1] * segment_c_duration
    total_energy_joules += energy_c
    total_emissions_g += (energy_c / JOULES_TO_KWH) * get_intensity_at(valid_m[-1][0], intensity_measurements)
    
    # Calculate the true mathematical average power
    avg_watt = total_energy_joules / duration_s
    
    return float(total_energy_joules), float(avg_watt), min_watt, max_watt, float(total_emissions_g)

def compute_epoch_stats(
    power_m: List[PowerMeasurementData], 
    intensity_m: List[IntensityMeasurementData], 
    start: datetime, 
    end: datetime
) -> SpanStats:
    """
    Computes system-level event statistics for an epoch by aggregating device-level integrations.
    """
    duration_s = (end - start).total_seconds()
    
    # Slice measurements for this span
    span_power = [m for m in power_m if start <= m.timestamp <= end]
    span_intensity = [m for m in intensity_m if start <= m.timestamp <= end]
    
    if not span_power or duration_s <= 0:
        return SpanStats(
            avg_watt=0.0, min_watt=0.0, max_watt=0.0,
            avg_intensity=0.0, min_intensity=0.0, max_intensity=0.0,
            power_usage_pr_device={}, emissions_g=0.0, power_usage_kwh=0.0,
            power_measurements_count=0, intensity_measurements_count=len(span_intensity)
        )
        
    # We pass the FULL intensity history for LOCF math to ensure we don't miss the 
    # intensity measurement that was active before the epoch started!
    full_intensity_tuples = [(m.timestamp, m.carbon_intensity) for m in intensity_m]
    
    device_series = {}
    for m in span_power:
        for device_name, power in m.power_usage_pr_device.items():
            if device_name not in device_series:
                device_series[device_name] = []
            device_series[device_name].append((m.timestamp, power))
            
    sys_total_energy_j = 0.0
    sys_total_emissions_g = 0.0
    sys_min_w = 0.0
    sys_max_w = 0.0
    device_usage_avg = {}
    
    for d_name, series in device_series.items():
        energy_j, avg_w, min_w, max_w, emissions_g = calculate_device_energy_and_emissions(
            device_name=d_name,
            power_measurements=series,
            intensity_measurements=full_intensity_tuples,
            t_start=start,
            t_stop=end
        )
        
        device_usage_avg[d_name] = avg_w
        sys_total_energy_j += energy_j
        sys_total_emissions_g += emissions_g
        sys_min_w += min_w
        sys_max_w += max_w
        
    sys_avg_w = sys_total_energy_j / duration_s
    sys_power_kwh = sys_total_energy_j / 3600000.0
    
    avg_i = 0.0
    min_i = 0.0
    max_i = 0.0
    if span_intensity:
        ints = [m.carbon_intensity for m in span_intensity]
        avg_i = sum(ints) / len(ints)
        min_i = min(ints)
        max_i = max(ints)
        
    return SpanStats(
        avg_watt=sys_avg_w,
        min_watt=sys_min_w,
        max_watt=sys_max_w,
        avg_intensity=avg_i,
        min_intensity=min_i,
        max_intensity=max_i,
        power_usage_pr_device=device_usage_avg,
        emissions_g=sys_total_emissions_g,
        power_usage_kwh=sys_power_kwh,
        power_measurements_count=len(span_power),
        intensity_measurements_count=len(span_intensity)
    )
