"""Entry point for the Live Spectrum tool (Phase 2).

Adds the V3 source project (read-only, never modified) and the destination
package to sys.path, then launches the Live Spectrum GUI.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# Destination package source.
sys.path.insert(0, os.path.join(_HERE, "src"))
# V3 source project (actual nRF24L01+ scanner implementation — read only).
sys.path.insert(0, os.path.join(_HERE, "..", "v3"))

from rf_spectrum_visualizer.ui.live_spectrum import main  # noqa: E402

if __name__ == "__main__":
    main()
