"""Public exceptions for GreenFleet AI.

Use these imports throughout the application::

    from src.exception import ValidationError
"""

from .exception import (
    ConfigurationError,
    ErrorDetail,
    GreenFleetError,
    InfeasibleSolutionError,
    OptimizationError,
    PredictionError,
    ValidationError,
)

__all__ = [
    "ConfigurationError",
    "ErrorDetail",
    "GreenFleetError",
    "InfeasibleSolutionError",
    "OptimizationError",
    "PredictionError",
    "ValidationError",
]
