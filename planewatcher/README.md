# plane watcher

![planewatcher_proto_1.1_render.png](assets/planewatcher_proto_1.1_render.png)

The **plane watcher** is our attempt at creating a hardware-based ADS-B receiver and decoder. It is a hat/cape/shield for a [HelloFPGA Smart ZYNQ SL](http://www.hellofpga.com/index.php/2023/05/10/smart-zynq-sl/) board.

The goal of the project is to make a reasonably priced yet high quality ADS-B receiver for hobbiests, that achieves high MLAT accuracy by including GPS timing and message decoding in hardware.


## Status

We are currently working on our first prototype. This is not yet ready for use. 

## Design

The design consists of these parts:

### RF Input

The signal from the antenna is amplified and filtered using two stages of LNA amplification and SAW filters centred on 1090MHz. 

### Log Detector

The amplified and filtered RF signal is fed into a log detector. This device shows the RF power level. With an oscilloscope on the output of this device, we can read the raw ADS-B pulses and decode them by hand. 

### ADC

The pulse output is fed into an analog to digital converter (ADC) through a differential driver. This allows digital sampling of the pulses.

### FPGA

The FPGA contains bytecode to perform the ADS-B decoding via discrete logic blocks. The FPGA decodes the pulses sampled by the ADC and decodes into usable ADS-B messages. 

