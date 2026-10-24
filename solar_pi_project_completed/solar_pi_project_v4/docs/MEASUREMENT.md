# Measurement

## Units
Voltage V, current mA and A, power W, energy Wh.

## Power source selection
The INA219 power register is used only when it agrees with V × I within 10 %;
otherwise V × I is used. This avoids trusting a miscalibrated register while
still using the more accurate register when calibration is sound.

## Energy integration
Trapezoidal rule over power × time. Max integration gap = 5 × sampling interval
(configurable). Never integrates across gaps, stop/start, or invalid samples.
Daily energy covers only monitored intervals. Integration state is persisted.