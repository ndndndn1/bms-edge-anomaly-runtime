# Requirements and acceptance evidence

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| API-01 | A supported versioned detection interface and compatibility route | `/v1/detect` and deprecated `/detect` in `src/main.py`; route equality test |
| API-02 | Strict finite/config/state validation | startup settings bounds, strict Pydantic model, native finite/dimension checks, negative tests |
| API-03 | Machine-readable errors | RFC 9457 fields and `application/problem+json` validation, 404, 413, and native error paths |
| ABI-01 | Stable native integration boundary | `bms_v1_*` C linkage, ABI version probe, status codes, compatibility wrappers |
| SAFE-01 | Deterministic OTA/isolation ordering | electrical trip precedence, latched isolation, explicit safe reset, reversible OTA hold |
| SAFE-02 | No direct hardware control | receive-only SocketCAN module; explicit docs boundary; no socket send or actuator API |
| CAN-01 | Linux CAN/CAN-FD ingestion | classic/FD SocketCAN decode and deterministic collector tests |
| CAN-02 | Reproducible hardware-free input | checked-in reference CAN profile with stable generated window |
| CAN-03 | PCAN-USB FD connection guidance | IPEH-004022/004023 Linux setup and safety boundary documentation |
| OPS-01 | Kubernetes-style health semantics | independent `/health/live` and `/health/ready`, plus compatibility `/health` |
| OPS-02 | Low-cardinality observability | Prometheus counters/sums and structured request logs without pack IDs/telemetry |
| SEC-01 | Least-privilege runtime | non-root UID 10001, read-only root, cap-drop ALL, no-new-privileges, bounded PID/memory |
| TEST-01 | Memory and undefined-behavior checks | ASan, UBSan, and leak detection in `scripts/verify_native.sh` and CI |
| TEST-02 | Resource and performance evidence | native size caps, HTTP declared-size cap, bounded benchmark and negative tests |
| QUAL-01 | Evidence-backed quality threshold | `quality/scorecard.json` score at least 80 and stdlib validator in CI |

The runtime deliberately leaves employment tenure and real production ownership as
`not_demonstrable`; repository evidence cannot establish those claims.
