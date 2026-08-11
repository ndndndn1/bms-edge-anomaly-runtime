import json
import os
import urllib.request


def post(payload: dict) -> dict:
    request = urllib.request.Request(
        os.getenv("BMS_ENDPOINT", "http://127.0.0.1:8801/v1/detect"),
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


base = {
    "pack_id": "smoke-pack",
    "timestamp_ms": 1,
    "cell_voltages": [[3.70 + (index % 3) * 0.001 for _ in range(8)] for index in range(32)],
    "pack_temp_c": [30.0] * 32,
}
normal = post(base)
assert normal["severity"] == "normal", normal
base["cell_voltages"][-1][3] = 4.40
critical = post(base)
assert critical["severity"] == "critical", critical
assert critical["worst_cell"] == 3, critical
print("BMS smoke passed")
