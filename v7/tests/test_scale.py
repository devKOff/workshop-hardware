# ------------------------------------------------------------------ y-scale
def test_nice_round_up():
    from rf_spectrum_visualizer.gui.theme import nice_round_up, Y_SCALE_MIN
    assert Y_SCALE_MIN == 30.0
    assert nice_round_up(3.0) == 30.0   # floor at 30
    assert nice_round_up(30.0) == 30.0
    assert nice_round_up(31.0) == 50.0
    assert nice_round_up(49.0) == 50.0
    assert nice_round_up(50.0) == 50.0
    assert nice_round_up(60.0) == 100.0
    assert nice_round_up(150.0) == 100.0


def test_y_scale_manager_auto():
    from rf_spectrum_visualizer.gui.theme import YScaleManager
    m = YScaleManager()
    assert m.mode == "auto"
    assert m.label() == "Activity % (scale 0-100)"
    # Grow immediately (multiplier 1.25 now)
    assert m.compute(8.0) == 30.0   # 8*1.25=10 -> max(30,10)=30 -> nice 30
    assert m.compute(24.0) == 30.0  # 24*1.25=30 -> max(30,30)=30 -> nice 30
    assert m.compute(25.0) == 50.0  # 25*1.25=31.25 -> nice 50
    assert m.label() == "Activity % (scale 0-50)"
    # Shrink slowly: hysteresis (shrink threshold = current * 0.7)
    m2 = YScaleManager()
    m2.compute(80.0)  # 80*1.25=100 -> nice 100
    assert m2.compute(55.0) == 100.0  # 55*1.25=68.75 -> nice 75, keep 100 (75 not < 70)
    assert m2.compute(40.0) == 50.0   # 40*1.25=50 -> nice 50, 50 < 70, shrink to 50


def test_y_scale_manager_fixed():
    from rf_spectrum_visualizer.gui.theme import YScaleManager
    m = YScaleManager()
    m.set_mode("fixed")
    assert m.compute(5.0) == 100.0
    assert m.label() == "Activity % (scale 0-100)"
    m.set_mode("auto")
    assert m.compute(3.0) == 30.0  # back to auto, floor at 30


def test_waterfall_cmap_constant():
    from rf_spectrum_visualizer.gui.theme import WATERFALL_CMAP
    assert WATERFALL_CMAP == "inferno"


# ------------------------------------------------------------------ ScanController state machine
def test_scan_controller_start_stop_start():
    from rf_spectrum_visualizer.scan_worker import ScanController
    c = ScanController()
    assert c.start_enabled
    assert not c.stop_enabled
    assert c.start() is True
    assert not c.start_enabled
    assert c.stop_enabled
    c.stop()
    assert c.start_enabled
    assert not c.stop_enabled
    assert c.start() is True  # can start again after stop


def test_scan_controller_start_complete_start():
    from rf_spectrum_visualizer.scan_worker import ScanController
    c = ScanController()
    assert c.start() is True
    assert not c.start_enabled
    c.complete()
    assert c.start_enabled
    assert c.start() is True


def test_scan_controller_start_error_start():
    from rf_spectrum_visualizer.scan_worker import ScanController
    c = ScanController()
    assert c.start() is True
    assert not c.start_enabled
    c.error()
    assert c.start_enabled
    assert c.start() is True


def test_scan_controller_rapid_start_stop():
    from rf_spectrum_visualizer.scan_worker import ScanController
    c = ScanController()
    for _ in range(10):
        assert c.start() is True
        assert not c.start_enabled
        assert c.stop_enabled
        c.stop()
        assert c.start_enabled


def test_scan_controller_double_start_blocked():
    from rf_spectrum_visualizer.scan_worker import ScanController
    c = ScanController()
    assert c.start() is True
    assert c.start() is False  # already scanning, blocked


# ------------------------------------------------------------------ Wi-Fi overlay
class _FakeSpan:
    def __init__(self):
        self.removed = False

    def remove(self):
        self.removed = True


class _FakeText:
    def __init__(self, t):
        self._text = t
        self.removed = False

    def get_text(self):
        return self._text

    def remove(self):
        self.removed = True


class _FakeAx:
    def __init__(self):
        self.spans = []
        self._wifi_spans = []
        self.texts = []
        self.ax_bar = self

    def axvspan(self, start, end, **kwargs):
        s = _FakeSpan()
        self.spans.append(s)
        return s

    def text(self, x, y, text, **kwargs):
        self.texts.append(_FakeText(text))

    def get_xaxis_transform(self):
        return "identity"


def test_wifi_bands_drawing():
    """_draw_wifi_bands should create 3 spans with correct nRF channel ranges."""
    from rf_spectrum_visualizer.gui.pages.live_spectrum import LiveSpectrumPage

    ax = _FakeAx()
    LiveSpectrumPage._draw_wifi_bands(ax, ax)
    assert len(ax.spans) == 3
    # Wi-Fi ch 1: nRF ~2-22 -> axvspan(1.5, 22.5)
    assert ax.spans[0] is not None
    # Wi-Fi ch 6: nRF ~27-47 -> axvspan(26.5, 47.5)
    assert ax.spans[1] is not None
    # Wi-Fi ch 11: nRF ~52-72 -> axvspan(51.5, 72.5)
    assert ax.spans[2] is not None
    # Labels present
    assert any("Wi-Fi ch 1" in t.get_text() for t in ax.texts)
    assert any("Wi-Fi ch 6" in t.get_text() for t in ax.texts)
    assert any("Wi-Fi ch 11" in t.get_text() for t in ax.texts)


def test_wifi_bands_remove():
    """_remove_wifi_bands should remove all spans and Wi-Fi text labels."""
    from rf_spectrum_visualizer.gui.pages.live_spectrum import LiveSpectrumPage

    ax = _FakeAx()
    LiveSpectrumPage._draw_wifi_bands(ax, ax)
    assert len(ax._wifi_spans) == 3

    LiveSpectrumPage._remove_wifi_bands(ax)
    assert all(s.removed for s in ax._wifi_spans)
    assert ax._wifi_spans == []
    # Wi-Fi labels should be marked removed
    wifi_texts = [t for t in ax.texts if "Wi-Fi ch" in t.get_text()]
    assert all(t.removed for t in wifi_texts)
    # Non-Wi-Fi labels should remain
    non_wifi = [t.get_text() for t in ax.texts if not t.removed]
    assert len(non_wifi) == 0  # All texts added by _draw_wifi_bands are Wi-Fi labels
