# ------------------------------------------------------------------ y-scale
def test_nice_round_up():
    from rf_spectrum_visualizer.gui.theme import nice_round_up, Y_SCALE_MIN
    assert Y_SCALE_MIN == 5.0
    assert nice_round_up(3.0) == 5.0   # floor at 5
    assert nice_round_up(5.0) == 5.0
    assert nice_round_up(10.0) == 10.0
    assert nice_round_up(11.0) == 20.0
    assert nice_round_up(19.0) == 20.0
    assert nice_round_up(21.0) == 25.0
    assert nice_round_up(25.0) == 25.0
    assert nice_round_up(30.0) == 50.0
    assert nice_round_up(60.0) == 100.0
    assert nice_round_up(150.0) == 100.0


def test_y_scale_manager_auto():
    from rf_spectrum_visualizer.gui.theme import YScaleManager
    m = YScaleManager()
    assert m.mode == "auto"
    assert m.label() == "Activity % (scale 0-100)"
    # Grow immediately (multiplier 1.15 now)
    assert m.compute(8.0) == 10.0   # 8*1.15=9.2 -> max(5,9.2)=9.2 -> nice 10
    assert m.compute(16.0) == 20.0  # 16*1.15=18.4 -> nice 20
    assert m.label() == "Activity % (scale 0-20)"
    # Shrink slowly: hysteresis (shrink threshold = current * 0.7)
    m2 = YScaleManager()
    m2.compute(80.0)  # 80*1.15=92 -> nice 100
    assert m2.compute(55.0) == 100.0  # 55*1.15=63.25 -> nice 75, keep 100 (75 not < 70)
    assert m2.compute(40.0) == 50.0   # 40*1.15=46 -> nice 50, 50 < 70, shrink to 50


def test_y_scale_manager_fixed():
    from rf_spectrum_visualizer.gui.theme import YScaleManager
    m = YScaleManager()
    m.set_mode("fixed")
    assert m.compute(5.0) == 100.0
    assert m.label() == "Activity % (scale 0-100)"
    m.set_mode("auto")
    assert m.compute(3.0) == 5.0  # back to auto, floor at 5


def test_waterfall_cmap_constant():
    from rf_spectrum_visualizer.gui.theme import WATERFALL_CMAP
    assert WATERFALL_CMAP == "inferno"


# ------------------------------------------------------------------ ScanState state machine
def test_scan_state_start_stop_start():
    from rf_spectrum_visualizer.scan_worker import ScanState
    c = ScanState()
    assert c.start_enabled
    assert not c.stop_enabled
    assert c.start() is True
    assert not c.start_enabled
    assert not c.stop_enabled  # STARTING: stop not yet enabled
    c.started()
    assert c.state == ScanState.RUNNING
    assert c.stop_enabled
    c.stop()
    assert c.state == ScanState.STOPPING
    assert not c.start_enabled
    assert not c.stop_enabled
    c.stopped()
    assert c.start_enabled
    assert not c.stop_enabled
    assert c.start() is True  # can start again after stop


def test_scan_state_start_complete_start():
    from rf_spectrum_visualizer.scan_worker import ScanState
    c = ScanState()
    assert c.start() is True
    c.started()
    assert not c.start_enabled
    c.complete()
    assert c.start_enabled
    assert c.start() is True


def test_scan_state_start_error_start():
    from rf_spectrum_visualizer.scan_worker import ScanState
    c = ScanState()
    assert c.start() is True
    c.started()
    assert not c.start_enabled
    c.error()
    assert c.start_enabled
    assert c.start() is True


def test_scan_state_rapid_start_stop():
    from rf_spectrum_visualizer.scan_worker import ScanState
    c = ScanState()
    for _ in range(10):
        assert c.start() is True
        c.started()
        assert not c.start_enabled
        assert c.stop_enabled
        c.stop()
        c.stopped()
        assert c.start_enabled


def test_scan_state_double_start_blocked():
    from rf_spectrum_visualizer.scan_worker import ScanState
    c = ScanState()
    assert c.start() is True
    assert c.start() is False  # already starting, blocked


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
