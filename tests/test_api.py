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


def test_normal_window() -> None:
    response = client.post("/detect", json=payload())
    assert response.status_code == 200
    assert response.json()["severity"] == "normal"


def test_voltage_spike_isolated() -> None:
    body = payload()
    body["cell_voltages"][-1][1] = 4.40
    response = client.post("/detect", json=body)
    assert response.status_code == 200
    assert response.json()["severity"] == "critical"
    assert response.json()["worst_cell"] == 1


def test_bad_window_rejected() -> None:
    body = payload()
    body["cell_voltages"].pop()
    assert client.post("/detect", json=body).status_code == 422
