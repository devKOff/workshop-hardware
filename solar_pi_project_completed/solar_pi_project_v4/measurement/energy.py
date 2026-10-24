"""Energy integration — re-exports from solar_monitor.core.energy."""

from __future__ import annotations

from solar_monitor.core.energy import (  # noqa: E402
    EnergyIntegrator,
    IntegrationState,
    SECONDS_PER_HOUR,
)

__all__ = ["SECONDS_PER_HOUR", "IntegrationState", "EnergyIntegrator"]
