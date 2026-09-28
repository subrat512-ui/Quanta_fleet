"""Persistence components for GreenFleet AI."""

__all__ = ["FuelCastMongoPreflight", "preflight_fuelcast_mongodb", "run_fuelcast_mongodb"]


def __getattr__(name):
    if name in __all__:
        from greenfleet.database import fuelcast
        return getattr(fuelcast, name)
    raise AttributeError(name)
