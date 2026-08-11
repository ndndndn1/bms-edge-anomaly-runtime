import importlib
import os

from fastapi.testclient import TestClient

os.environ["BMS_WINDOW"] = "6"
os.environ["BMS_CELLS"] = "2"
main = importlib.import_module("src.main")
client = TestClient(main.app)


def payload() -> dict:
    return {
        "pack_id": "pack-1",
        "timestamp_ms": 1,
        "cell_voltages": [[3.70, 3.71] for _ in range(6)],
        "pack_temp_c": [30.0] * 6,
    }


def test_versioned_and_compatibility_routes_match() -> None:
    versioned = client.post("/v1/detect", json=payload())
    compatibility = client.post("/detect", json=payload())
    assert versioned.status_code == 200
    assert versioned.json() == compatibility.json()
    assert versioned.json()["api_version"] == "v1"
    assert versioned.json()["severity"] == "normal"


def test_voltage_spike_latches_native_isolation() -> None:
    body = payload()
    body["cell_voltages"][-1][1] = 4.40
    response = client.post("/v1/detect", json=body)
    assert response.status_code == 200
    assert response.json()["severity"] == "critical"
    assert response.json()["worst_cell"] == 1
    assert response.json()["safety_state"] == "isolate_latched"


def test_isolation_requires_explicit_safe_reset() -> None:
    body = payload()
    body["current_safety_state"] = "isolate_latched"
    assert client.post("/v1/detect", json=body).json()["safety_state"] == "isolate_latched"
    body["reset_requested"] = True
    assert client.post("/v1/detect", json=body).json()["safety_state"] == "normal"


def test_ota_hold_is_reversible_and_cannot_override_trip() -> None:
    body = payload()
    body["ota_requested"] = True
    assert client.post("/v1/detect", json=body).json()["safety_state"] == "ota_hold"
    body["cell_voltages"][-1][0] = 4.30
    assert client.post("/v1/detect", json=body).json()["safety_state"] == "isolate_latched"


def test_bad_window_is_rfc9457_problem() -> None:
    body = payload()
    body["cell_voltages"].pop()
    response = client.post("/v1/detect", json=body)
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 422
    assert response.json()["instance"] == "/v1/detect"
    assert response.json()["errors"]


def test_strict_schema_rejects_extra_and_non_finite_values() -> None:
    body = payload()
    body["unexpected"] = True
    assert client.post("/v1/detect", json=body).status_code == 422
    body = payload()
    body["pack_temp_c"][0] = "30.0"
    assert client.post("/v1/detect", json=body).status_code == 422
    response = client.post(
        "/v1/detect",
        content=(
            '{"pack_id":"pack-1","timestamp_ms":1,'
            '"cell_voltages":[[3.7,3.71],[3.7,3.71],[3.7,3.71],'
            '[3.7,3.71],[3.7,3.71],[3.7,3.71]],'
            '"pack_temp_c":[NaN,30.0,30.0,30.0,30.0,30.0]}'
        ),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
