# PCAN-USB FD receive-only connection

This reference supports PEAK-System PCAN-USB FD **IPEH-004022** (USB-A) and
**IPEH-004023** (USB-C) through the Linux SocketCAN interface. The manufacturer lists Linux
drivers, CAN 2.0 A/B and CAN FD support, a 9-pin D-Sub CAN connector, and galvanic isolation up to
500 V. Confirm the current pinout and installation requirements against the
[official product page](https://www.peak-system.com/products/hardware/external-pc-interfaces/pcan-usb-fd/)
and [current user manual](https://www.peak-system.com/produktcd/Pdf/English/PCAN-USB-FD_UserMan_eng.pdf).

## Safety boundary

This bridge is receive-only evidence tooling. It never transmits a CAN/CAN-FD frame and does not
control contactors, isolation circuits, balancing hardware, chargers, inverters, MCUs, or OTA
bootloaders. API actions are recommendations for an independently engineered and validated safety
controller. Do not connect a development host directly to an energized traction battery. A
qualified engineer must provide isolation, correct bus termination, fused test power, wiring,
lockout/tagout, and a bench or HIL environment appropriate to the pack.

## Linux connection

Use the in-kernel `peak_usb` SocketCAN driver when it supports the adapter. Identify the interface
without changing it:

```bash
ip -details link show type can
```

The following values are examples, not pack-specific settings. Obtain arbitration/data bit rates
and ISO/non-ISO CAN-FD mode from the approved network specification before bringing up `can0`:

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 dbitrate 2000000 fd on
sudo ip link set can0 up
ip -details -statistics link show can0
```

Start the API and then the receive-only bridge:

```bash
python -m src.can_bridge --interface can0 --endpoint http://127.0.0.1:8801/v1/detect
```

No elevated privileges are required after the interface has been configured. Do not grant the
runtime `CAP_NET_ADMIN`; interface configuration belongs to host operations.

## Deterministic vcan/reference check

The checked-in profile exercises the same collector without hardware or network writes:

```bash
python -m src.can_bridge --mock config/reference-can-profile.json --no-submit
```

For a manual `vcan0` receiver check, create the interface on a disposable test host and run the
bridge with `--interface vcan0`. Any test frame transmitter is deliberately outside this project;
keeping generation separate makes the runtime's receive-only boundary reviewable.
