# BMS Edge Anomaly Runtime

A hardened, host-executable reference runtime for battery telemetry anomaly detection. It combines
a versioned C ABI, deterministic safety recommendations, a strict FastAPI contract, and a
receive-only Linux SocketCAN bridge. It intentionally contains no untrained model weights and no
code capable of controlling contactors, balancing hardware, chargers, MCUs, or OTA bootloaders.

## Detection contract

`POST /v1/detect` is the supported endpoint. `POST /detect` remains as a deprecated compatibility
alias with the same request and response. Invalid requests use RFC 9457-style
`application/problem+json` responses. Input is finite, dimensioned, physically bounded, strict
typed, and rejects unknown fields.

The checked-in profile produces and submits an executable complete 32-step request:

```bash
python3 -m src.can_bridge --mock config/reference-can-profile.json \
  --endpoint http://127.0.0.1:8801/v1/detect
```

The response includes an anomaly score, severity, worst cell, native safety state, and a
`recommended_action`. Recommendations are not actuator commands. The OpenAPI schema at
`/openapi.json` defines the direct JSON request and response shapes.

Safety states are deterministic:

- electrical limits always enter `isolate_latched`;
- isolation stays latched until `reset_requested=true` under hysteresis recovery limits;
- `ota_hold` is active only while OTA is requested and cannot override isolation.

## Run and verify

```bash
docker compose up -d --build --wait
python3 smoke.py
docker compose down
```

The API binds only to `127.0.0.1:8801`. The container runs as UID/GID 10001, with a read-only root
filesystem, all Linux capabilities dropped, `no-new-privileges`, PID/memory limits, and proxy-only
network placement. `proxy-net` and the host `squid-proxy` must already exist.

```bash
docker build --target test -t bms-edge-anomaly-runtime:test .
docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev \
  --cap-drop ALL --security-opt no-new-privileges bms-edge-anomaly-runtime:test
./scripts/verify_native.sh
python3 quality/check_score.py
```

`verify_native.sh` runs ASan, UBSan, leak detection, native boundary/resource tests, and a bounded
100,000-window benchmark. It is a quick regression check, not a production endurance soak.

## Operations

- `GET /health/live`: process liveness only.
- `GET /health/ready`: native ABI/config readiness.
- `GET /health`: compatibility alias for readiness.
- `GET /metrics`: Prometheus text metrics with route, status-class, and severity labels only.
- Logs are one-line JSON with request ID, method, bounded route template, status, and duration. Pack
  IDs and telemetry are excluded.

See the canonical [enterprise requirements](docs/enterprise-requirements.md), detailed
[acceptance evidence](docs/requirements.md), [quality scorecard](docs/quality-scorecard.md),
[operations](docs/operations.md), and
[PCAN-USB FD connection guidance](docs/pcan-usb-fd.md). The checked-in scorecard is validated in CI.

## Limits

This is not a certified ECU binary or a pack-specific safety controller. Thresholds, bit rates,
CAN identifiers, wiring, BSP/RTOS integration, watchdog behavior, diagnostics, and fault handling
require review and validation against the intended battery, vehicle, and safety process.
