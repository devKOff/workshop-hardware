
# ------------------------------------------------------------------ y-scale
def test_nice_round_up():
    from rf_spectrum_visualizer.gui.theme import nice_round_up
    assert nice_round_up(5.0) == 10.0
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
    # Grow immediately
    assert m.compute(8.0) == 10.0   # 8*1.25=10 -> nice 10
    assert m.compute(16.0) == 20.0  # 16*1.25=20 -> nice 20
    assert m.label() == "Activity % (scale 0-20)"
    # Shrink slowly: hysteresis (shrink threshold = current * 0.7)
    m2 = YScaleManager()
    m2.compute(80.0)  # 80*1.25=100 -> nice 100
    assert m2.compute(55.0) == 100.0  # 55*1.25=68.75 -> nice 75, 75 < 70? No, keep 100
    assert m2.compute(40.0) == 50.0   # 40*1.25=50 -> nice 50, 50 < 70, shrink to 50


def test_y_scale_manager_fixed():
    from rf_spectrum_visualizer.gui.theme import YScaleManager
    m = YScaleManager()
    m.set_mode("fixed")
    assert m.compute(5.0) == 100.0
    assert m.label() == "Activity % (scale 0-100)"
    m.set_mode("auto")
    assert m.compute(3.0) == 10.0  # back to auto
