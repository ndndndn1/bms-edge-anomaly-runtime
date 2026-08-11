# Enterprise requirements

This is the canonical enterprise contract for the runtime. The detailed, test-linked acceptance
matrix is maintained in [requirements.md](requirements.md).

## Target, input, and output

- **Target:** Linux userspace on x86_64/ARM64 with SocketCAN; PEAK PCAN-USB FD
  IPEH-004022/004023 is the documented reference adapter.
- **Production input:** receive-only classic CAN or CAN-FD frames decoded into a finite 32 x 8
  telemetry window, or the equivalent strict JSON request sent to `POST /v1/detect`.
- **Mock input:** `config/reference-can-profile.json`, consumed with
  `python3 -m src.can_bridge --mock ...`; no adapter or battery is required.
- **Output:** anomaly score, severity, worst-cell index, deterministic safety state, and a
  recommendation. Outputs are advisory and never actuator or contactor commands.

The runtime boundary, failure behavior, resource limits, and acceptance evidence are defined by
the requirements matrix linked above. Hardware wiring and interface instructions are in
[pcan-usb-fd.md](pcan-usb-fd.md).
