# Board Bring-Up Instructions: Rev proto 1.2

## Safety Notes

* Use ESD precautions when handling U7, U8, U9, U10, U11, and U1.
* Do not attach or remove the FPGA board while either board is powered.
* Remove power and confirm the rails have discharged before fitting components or changing board connections.
* For board-only testing, use a current-limited bench supply:
  * Start with the supply set to 0V.
  * Suggested first power-up limit, with U7, U8, U9, U10, U11, and U1 removed: 100mA.
  * Suggested second power-up limit, after fitting U7, U8, U9, U10, and U11: 300mA.
  * Record the steady-state current at each stage. Increase the limit only if the measured current is understood.
* Stop immediately if the supply hits current limit, a rail collapses, a measured voltage is out of tolerance, or any IC/regulator becomes hot.
* Use a DMM or 10x high-impedance oscilloscope probe for TP13, TP16, TP17, and TP21. Do not use 50 ohm scope termination on these points.

## Visual Checks

### Check Soldering

* Where possible, check solder joints under microscope and ensure no dry joints.
* Ensure no tombstoned components.

### Component Orientation

With the board oriented component side up, and the RF_IN connector facing left:

* U7 pin 1 should be bottom side, leftmost pin
* FL1 pin 1 should be left side, topmost pin
* U8 pin 1 should be top side, rightmost pin
* FL2 pin 1 should be left side, topmost pin
* U9 pin 1 should be bottom side, leftmost pin
* U10 pin 1 should be top side, rightmost pin
* U11 pin 1 should be top side, rightmost pin
* LED1-5 common anode (+) should be top side, leftmost pin
* U6 pin 1 should be right side, bottommost pin
* Q1 pin 1 (gate) should be bottom pin
* LED6 anode (+) should be left pin
* U1 module pin 1 should be left side, topmost pin

All other components should not be polarised.

## Board Bring-Up

### Before First Power-Up

* Remove expensive components before first bring-up:
  * U7 LNA, TQP3M9036
  * U8 LNA, TQP3M9036
  * U9 log detector, ADL5513
  * U10 ADC driver, AD8138
  * U11 ADC, AD9203
  * U1 GPS module
* Do not attach to the FPGA board.
* Resistance checks, with the board unpowered: ensure there are no dead shorts or unexpectedly low resistance readings.
  * Place black probe on pin 36 of connector J4 (GND)
  * Check resistance to:
    * pin 38 of connector J4 (FPGA_3V3)
    * pin 40 of connector J4 (FPGA_VCC)
    * TP20 (5V input)
    * TP11 (3V3)
    * TP1 (3V3A)
    * TP14 (TADJ)
    * TP15 (VOCM)
  * The reading may move while capacitors charge. The check is for a hard short or low-ohm fault, not necessarily a perfect open circuit.

### First Power-Up

* Apply power to board
  * GND to pin 35/36 of connector J4
  * Current-limited 5V to pin 39/40 of connector J4
  * Start at 0V, current limit 100mA, then ramp up to 5V
  * Stop immediately if the supply reaches current limit, a rail is low, or anything heats unexpectedly
* Multimeter checks: check voltages
  * Place black probe on pin 36 of connector J4 (GND)
  * Set to DC voltage
  * Place red probe on TP20, ensure 5V
  * Place red probe on TP11, ensure 3.3V
  * Place red probe on TP1, ensure 3.3V
  * Place red probe on TP14, ensure about 0.80V to 0.87V
  * Place red probe on TP15, ensure about 1.65V
  * Record the input current
* Remove power

### Replace removed components

* U7 LNA
* U8 LNA
* U9 Log Detector
* U10 ADC Driver
* U11 ADC
* Leave U1 GPS module removed.
* Leave FPGA board disconnected.
* Inspect the newly fitted parts under microscope before applying power.
* Repeat resistance checks, with the board unpowered:
  * Place black probe on pin 36 of connector J4 (GND)
  * Check TP20, TP11, TP1, TP14, TP15, and TP21
  * Ensure there are no dead shorts or unexpectedly low resistance readings

### Second Power-Up

* Apply power to board
  * GND to pin 35/36 of connector J4
  * Current-limited 5V to pin 39/40 of connector J4
  * Start at 0V, current limit 300mA, then ramp up to 5V
  * Stop immediately if the supply reaches current limit, a rail is low, or anything heats unexpectedly
  * U11 digital outputs are unloaded while the FPGA board is disconnected. This should not damage U11.
* Multimeter checks as before: check voltages
  * Place black probe on pin 36 of connector J4 (GND)
  * Set to DC voltage
  * Place red probe on TP20, ensure 5V
  * Place red probe on TP11, ensure 3.3V
  * Place red probe on TP1, ensure 3.3V
  * Place red probe on TP14, ensure about 0.80V to 0.87V
  * Place red probe on TP15, ensure about 1.65V
* New multimeter checks: check voltage
  * Place black probe on pin 36 of connector J4 (GND)
  * Set to DC voltage
  * Check TP21 with a DMM or 10x high-impedance probe only. Ensure about 1V.
* Scope checks
  * Optimum TADJ voltage
    * Connect probe ground to board ground
    * Probe TP13 using a 10x high-impedance probe. Do not use 50 ohm termination.
    * ADS-B pulses on baseband should appear when RF-IN is connected.
    * Adjust RV1 from minimum to maximum while observing.
    * Determine optimum RV1 setting.
    * Measure and record voltage at TP14 allowing RV1 to be removed, and R26/R27 voltage divider to be adjusted accordingly in next revision.
  * Differential signal
    * Connect probe grounds to board ground
    * Probe 10x CH1 on TP16
    * Probe 10x CH2 on TP17
    * Do not connect a probe ground clip to TP16 or TP17
    * Check TP16 and TP17 individually first. Each should sit near TP15, about 1.65V, and remain within the 0V to 3.3V ADC input range.
    * Enable math: CH1 - CH2. Math trace is the differential signal being driven toward the ADC.
    * Output should resemble ADS-B baseband pulses when a suitable 1090MHz signal is present.
    * This is what the ADC sees
* Remove power

### Third Power-Up

* FPGA attachment gates:
  * Confirm the FPGA board is Smart ZYNQ SL V1.2/V1.3.
  * Confirm FPGA bank 33 VCCO is 3.3V.
  * Confirm FPGA bank 35 VCCO is 3.3V.
  * Confirm the FPGA design sets ADC data and OTR pins as inputs or high impedance before the ADC can drive them.
  * Confirm the FPGA design drives ADC CLK.
  * Confirm GPS TX and PPS pins are FPGA inputs or high impedance.
  * Confirm GPS RX and GPS reset are driven by the FPGA.
  * Confirm the bench supply is disconnected from J4.
  * Confirm both boards are unpowered before mating.
  * Confirm the headers are aligned correctly before applying power.
* Attach to FPGA board.
* Power FPGA board.
* Stop immediately if the FPGA supply reports over-current, a rail is low, or anything heats unexpectedly.
* Multimeter checks: check voltages
  * Place black probe on pin 36 of connector J4 (GND)
  * Set to DC voltage
  * Place red probe on TP20, ensure 4.5V - 5V
  * Place red probe on TP11, ensure 3.3V
  * Place red probe on TP1, ensure 3.3V
  * Place red probe on TP14, ensure about 0.80V to 0.87V
  * Place red probe on TP15, ensure about 1.65V
  * Check TP21 with a DMM or 10x high-impedance probe only. Ensure about 1V.
  * Check U1 pin 6 pad, ensure 3.3V
* Remove power
* Detach from FPGA board.
* Fit GPS module.
* Attach GPS antenna.

### Fourth Power-Up

* Repeat the FPGA attachment gates from Third Power-Up.
* Attach to FPGA board.
* Power FPGA board.
* Stop immediately if the FPGA supply reports over-current, a rail is low, or anything heats unexpectedly.
* Multimeter checks: check voltages
  * Place black probe on pin 36 of connector J4 (GND)
  * Set to DC voltage
  * Place red probe on TP20, ensure 4.5V - 5V
  * Place red probe on TP11, ensure 3.3V
  * Place red probe on TP1, ensure 3.3V
  * Place red probe on TP14, ensure about 0.80V to 0.87V
  * Place red probe on TP15, ensure about 1.65V
  * Check TP21 with a DMM or 10x high-impedance probe only. Ensure about 1V.
  * Check GPS module pin 6, ensure 3.3V
* Confirm LED6 flashes at 1Hz, indicating PPS.
* Confirm FPGA can interface with ADC and GPS.
* Test RGB LEDs.

## Next steps if we get this far

* Celebrate
* Play with NanoVNA to tune RF section
