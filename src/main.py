from __future__ import annotations

import ctypes
import math
import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

WINDOW = int(os.getenv("BMS_WINDOW", "32"))
CELL_CHANNELS = int(os.getenv("BMS_CELLS", "8"))
WARN_SCORE = float(os.getenv("BMS_WARN_SCORE", "8.0"))
CRITICAL_SCORE = float(os.getenv("BMS_CRITICAL_SCORE", "20.0"))


class Core:
    def __init__(self) -> None:
        library = Path(os.getenv("BMS_CORE_LIBRARY", "/app/libbms_core.so"))
        self._lib = ctypes.CDLL(str(library))
        self._lib.bms_anomaly_score.restype = ctypes.c_double
        self._lib.bms_anomaly_score.argtypes = [
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]

    def score(self, matrix: list[list[float]]) -> tuple[float, int]:
        flat = [value for row in matrix for value in row]
        values = (ctypes.c_double * len(flat))(*flat)
        worst = ctypes.c_size_t()
        score = self._lib.bms_anomaly_score(values, len(matrix), len(matrix[0]), ctypes.byref(worst))
        if score < 0 or not math.isfinite(score):
            raise ValueError("native detector rejected telemetry")
        return float(score), int(worst.value)


class TelemetryWindow(BaseModel):
    pack_id: str = Field(min_length=1, max_length=64)
    timestamp_ms: int = Field(ge=0)
    cell_voltages: list[list[float]]
    pack_temp_c: list[float]

    @field_validator("cell_voltages")
    @classmethod
    def validate_cells(cls, value: list[list[float]]) -> list[list[float]]:
        if len(value) != WINDOW:
            raise ValueError(f"cell_voltages must contain {WINDOW} steps")
        if any(len(row) != CELL_CHANNELS for row in value):
            raise ValueError(f"every step must contain {CELL_CHANNELS} cells")
        if any(not 0.0 < cell < 6.0 for row in value for cell in row):
            raise ValueError("cell voltage is outside the measurable range")
        return value

    @field_validator("pack_temp_c")
    @classmethod
    def validate_temperature(cls, value: list[float]) -> list[float]:
        if len(value) != WINDOW:
            raise ValueError(f"pack_temp_c must contain {WINDOW} steps")
        return value


core = Core()
app = FastAPI(title="BMS edge anomaly runtime", version="1.0.0")


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "detector": "native-robust-delta", "window": WINDOW, "cells": CELL_CHANNELS}


@app.post("/detect")
def detect(window: TelemetryWindow) -> dict[str, object]:
    score, channel = core.score(window.cell_voltages)
    max_voltage = max(max(row) for row in window.cell_voltages)
    max_temperature = max(window.pack_temp_c)
    electrical_trip = max_voltage > 4.25 or max_temperature > 60.0
    if electrical_trip or score >= CRITICAL_SCORE:
        severity, action = "critical", "isolate_cells"
    elif score >= WARN_SCORE:
        severity, action = "warn", "halt_balancing"
    else:
        severity, action = "normal", "continue"
    return {
        "pack_id": window.pack_id,
        "timestamp_ms": window.timestamp_ms,
        "score": round(score, 4),
        "severity": severity,
        "worst_cell": channel,
        "max_cell_voltage": max_voltage,
        "max_pack_temperature": max_temperature,
        "recommended_action": action,
    }
