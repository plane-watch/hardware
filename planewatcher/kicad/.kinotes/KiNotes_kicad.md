# **kicad - Design Notes**

## **Overview**

<!-- Brief description of the PCB project -->

## **Schematic Notes**

<!-- Key circuit blocks, design rationale -->

## **Layout Considerations**

<!-- Layer stackup, impedance, keep-outs -->

## **Component Notes**

<!-- Click on designators like R1, C5, U3 to highlight on PCB -->

## **Power Distribution**

<!-- Power rails, decoupling strategy -->

## **Signal Integrity**

<!-- Critical nets, routing constraints -->

## Bring-Up

### Power Supplies

#### Input protection & filtering

* Populate components:

  * **J1** - Provides the external DC power input connection.
  * **F1** - Provides resettable overcurrent protection at the board power input.
  * **D2** - Clamps input supply transients on the protected power input.
  * **Q1** - Implements low-loss reverse-polarity protection on the board input.
  * **D1** & R36 - Limit P-channel MOSFET gate-source voltage during reverse/input transients.
  * **C68**, **L11**, **C69** - Pi filter & bulk capacitance for input power.
* Tests once fitted:

  * Apply reverse polarity 12V to input at **J1** with modest current limit. Stop on current limit.
  * Voltage at **TP20** referenced to GND should be 0V, indicating reverse polarity protection is working.
  * Apply correct polarity 12V to input at **J1**.
  * Voltage at **TP20** referenced to GND should be 12V.

#### 5V RF Power

Populate components:

* **C1**, **L1**, **C2** - Pi filter for regulator input.
* **C3** - high frequency bypass for switching regulator **U1**.
* **C6** - Soft-start / regulator control bypass capacitor for switching regulator **U1**.
* **R2** - Resistor setting the switching frequency of switching regulator **U1** to approximately 700kHz.
* **C8** - Switching regulator **U1** INTVCC bypass capacitor in the low-noise pre-regulator stage.
* **C4** - Switching regulator **U1** BST-to-SW bootstrap capacitor for the high-side switch gate drive.
* **R8** - Switching regulator **U1** power-good pull-up or regulator status bias resistor.
* **L2** - Switching regulator **U1** buck switching inductor.
* **C5** - Switching regulator **U1** output bulk capacitor on VPRE.
* R1 - Protection for switching regulator **U1**: VMAXLDOIN = 16.5V.
* R3, R4 - Set output of switching regulator **U1** to VOUT + 1V.
* C9, R5 - Set output of linear regulator U2 to 5V.
* R6 - Set maximum output current for linear regulator U2.
* C7 - Linear regulator U2 output bulk capacitor for LDO stability and load transients.
* R7 - Switching regulator **U1** power-good pull-up or regulator status bias resistor.

Tests once fitted:

* Apply correct polarity 12V to input at **J1**.
* Voltage at **TP3** referenced to GND should be 12V (PG_PRE).
* Voltage at **TP1** referenced to GND should be 6V (VPRE).
* Voltage at **TP4** referenced to GND should be 6V (PG_OUT).
* Voltage at **TP2** referenced to GND should be 5V (VOUT).

## **TODO**

- LT3045‑1 PGFB tied to VPRE (pin 7 → /Power_5V_RF/VPRE, etc.). The user note confirms intent: "PG = VPRE good, 0 = no input power." That's diagnostically weak — PG just echoes input presence, not whether the LDO is in regulation. For ~zero extra cost, tying PGFB to a fraction of OUT via a divider would make PG signal real output regulation. Up to you whether that matters for this project.
- **LT8640**‑1 SYNC/MODE floating (U12 pin 17) — datasheet allows this for the ‑1 variant (defaults to FCM), but it leaves spread‑spectrum disabled on the FPGA rail. Inconsistent with the LT8608 stages which use SSFM. Tying SYNC/MODE to INTVcc (pin 2) via 0 Ω would extend SSFM coverage to U12. Probably not impactful because the FPGA load isn't on the RF path, but cheap to add.
- **LT8608** EN/UV tied directly to VIN. Functionally fine (always enabled while VIN > ~1 V EN threshold), but you've thrown away the precise programmable UVLO. A 2‑resistor divider would give a clean turn‑on point (e.g. 8 V) —useful if you want a deterministic startup on a slow 12 V rise.

---

*KiNotes - PCBtools.xyz*
