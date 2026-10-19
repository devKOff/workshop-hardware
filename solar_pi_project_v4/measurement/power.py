"""Power source selection — re-exports from solar_monitor.core.power."""

from __future__ import annotations

from solar_monitor.core.power import (  # noqa: E402
    REGISTER_TOLERANCE,
    attach_power,
    compute_power,
)

__all__ = ["REGISTER_TOLERANCE", "attach_power", "compute_power"]
