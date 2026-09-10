from dataclasses import dataclass


@dataclass
class VesselRecord:

    # Time
    index: int

    # Ship
    speed_over_ground: float
    speed_through_water: float
    heading: float
    bearing: float

    # Environment
    sea_floor_depth: float

    # Weather
    temperature: float
    wind_speed: float
    wind_direction: float
    wave_height: float 
    wave_direction: float
    wave_period: float
    ocean_current_velocity: float
    ocean_current_direction: float

    # Target
    total_momentary_fuel: float