# BMS Edge Anomaly Runtime

A deployable battery telemetry gate that combines a portable C++ core with a typed FastAPI
interface. It demonstrates CAN payload decoding, deterministic safety transitions, and anomaly
detection without treating untrained neural-network weights as a working model.

## Flow

1. A gateway sends a fixed-size window of decoded cell voltages and pack temperature.
2. Pydantic rejects malformed dimensions and physically impossible cell voltages.
3. The API calls the compiled C++ detector through `ctypes`.
4. The detector computes robust per-channel delta scores and identifies the worst cell.
5. Electrical limits and the score determine `normal`, `warn`, or `critical` plus an action.

The C++ library also contains an eight-byte CAN cell-frame decoder and an explicit safety state
machine for isolation and OTA hold behavior. Hardware register access remains board-specific; the
portable core is exercised on the host and can be cross-compiled with a board support package.

## Run

```bash
docker compose up -d --build --wait
python3 smoke.py
docker compose down
```

The API is bound only to `127.0.0.1:8801`. `GET /health` reports the active deterministic detector.

## Test

```bash
docker compose run --rm test
docker build --target build .
```

Tests cover native CAN decoding, safety states, normal telemetry, a single-cell voltage spike, and
schema rejection. The runtime contains no randomly initialized model. A trained embedded model can
be added later only as a separately validated detector mode with versioned weights and an explicit
health state.

## Limits

- This is a host-executable reference core, not a certified ECU binary.
- Board startup, interrupt handlers, and the selected RTOS port belong in the target BSP.
- Thresholds require calibration against representative battery packs before production use.
