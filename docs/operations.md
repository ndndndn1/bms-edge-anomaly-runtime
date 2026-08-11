# Operations

## Startup configuration

Configuration is validated before the server becomes ready. Invalid, non-finite, or inconsistent
values fail startup.

| Variable | Default | Constraint |
| --- | ---: | --- |
| `BMS_WINDOW` | 32 | 3 through 4096 |
| `BMS_CELLS` | 8 | 1 through 512; reference CAN bridge requires even |
| `BMS_WARN_SCORE` | 8 | finite, nonnegative, below critical |
| `BMS_CRITICAL_SCORE` | 20 | finite, above warning |
| `BMS_MAX_BODY_BYTES` | 262144 | 1024 through 10485760 |
| `BMS_CORE_LIBRARY` | `/app/libbms_core.so` | existing file with ABI 1.0 |

The application rejects a declared body larger than `BMS_MAX_BODY_BYTES`. Production ingress must
also reject chunked/undeclared bodies above that limit before forwarding, because an HTTP
application cannot reliably bound bytes already buffered by every possible upstream server.

## Probes and metrics

Use `/health/live` only to decide whether the process should restart. Use `/health/ready` to decide
whether traffic may be routed. Scrape `/metrics`; do not add pack, cell, request ID, or error detail
labels. Request IDs belong in logs for correlation and are intentionally absent from metrics.

## Deployment boundary

Compose publishes only localhost port 8801 and routes container egress through the pre-existing
`proxy-net`/Squid path. A remote client should use an authenticated SSH or mesh/VPN path rather than
exposing the service. The application has no authentication layer; place it behind an approved
identity-aware gateway if multiple principals can reach it.

The repository's benchmark is short and deterministic. Before production, define pack-specific
latency/error SLOs and run an independently reviewed soak/load plan in an isolated environment. No
long soak is started by the standard verification script.
