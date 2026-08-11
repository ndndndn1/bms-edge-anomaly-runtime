# Enterprise quality scorecard

The machine-enforced source of truth is [`quality/scorecard.json`](../quality/scorecard.json).
CI validates its arithmetic, 80-point threshold, evidence paths, and all hard gates.

| Category | Maximum | Earned | Principal evidence |
| --- | ---: | ---: | --- |
| Correctness | 25 | 24 | native and API positive/negative tests |
| Interface contract | 15 | 14 | versioned HTTP and C ABI contracts |
| Functional safety boundary | 20 | 18 | state-machine tests and receive-only bridge |
| Operability | 15 | 14 | health, metrics, logs, and Compose runtime |
| Security | 10 | 9 | least-privilege image and pinned CI |
| Verification and docs | 15 | 14 | sanitizers, leak check, benchmark, examples |
| **Total** | **100** | **93** | target: **80** |

All mandatory gates—tests, runtime smoke, memory checks, security checks, and documentation
examples—must remain true. A numeric score cannot compensate for a failed hard gate.
