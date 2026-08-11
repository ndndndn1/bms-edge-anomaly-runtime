from __future__ import annotations

import ctypes
import json
import logging
import math
import os
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from starlette.exceptions import HTTPException

MAX_NATIVE_STEPS = 4096
MAX_NATIVE_CHANNELS = 512
ABI_VERSION = 0x00010000
LOGGER = logging.getLogger("bms.runtime")
logging.basicConfig(level=os.getenv("BMS_LOG_LEVEL", "INFO"), format="%(message)s")


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be finite and between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class Settings:
    window: int
    cells: int
    warn_score: float
    critical_score: float
    core_library: Path
    max_body_bytes: int

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls(
            window=_env_int("BMS_WINDOW", 32, 3, MAX_NATIVE_STEPS),
            cells=_env_int("BMS_CELLS", 8, 1, MAX_NATIVE_CHANNELS),
            warn_score=_env_float("BMS_WARN_SCORE", 8.0, 0.0, 1_000_000.0),
            critical_score=_env_float("BMS_CRITICAL_SCORE", 20.0, 0.0, 1_000_000.0),
            core_library=Path(os.getenv("BMS_CORE_LIBRARY", "/app/libbms_core.so")),
            max_body_bytes=_env_int("BMS_MAX_BODY_BYTES", 262_144, 1024, 10_485_760),
        )
        if settings.warn_score >= settings.critical_score:
            raise RuntimeError("BMS_WARN_SCORE must be lower than BMS_CRITICAL_SCORE")
        if not settings.core_library.is_file():
            raise RuntimeError(f"BMS_CORE_LIBRARY is not a file: {settings.core_library}")
        return settings


SETTINGS = Settings.from_env()


class NativeCoreError(RuntimeError):
    pass


class Core:
    def __init__(self, library: Path) -> None:
        self._lib = ctypes.CDLL(str(library))
        self._lib.bms_v1_abi_version.restype = ctypes.c_uint32
        self._lib.bms_v1_abi_version.argtypes = []
        actual_abi = int(self._lib.bms_v1_abi_version())
        if actual_abi != ABI_VERSION:
            raise RuntimeError(f"native ABI mismatch: expected {ABI_VERSION:#x}, got {actual_abi:#x}")
        self.abi_version = actual_abi

        self._lib.bms_v1_anomaly_score.restype = ctypes.c_int32
        self._lib.bms_v1_anomaly_score.argtypes = [
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self._lib.bms_v1_next_safety_state.restype = ctypes.c_int32
        self._lib.bms_v1_next_safety_state.argtypes = [
            ctypes.c_int32,
            ctypes.c_double,
            ctypes.c_double,
            ctypes.c_int32,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int32),
        ]

    def score(self, matrix: list[list[float]]) -> tuple[float, int]:
        flat = [value for row in matrix for value in row]
        values = (ctypes.c_double * len(flat))(*flat)
        score = ctypes.c_double()
        worst = ctypes.c_size_t()
        status = self._lib.bms_v1_anomaly_score(
            values, len(matrix), len(matrix[0]), ctypes.byref(score), ctypes.byref(worst)
        )
        if status != 0 or score.value < 0 or not math.isfinite(score.value):
            raise NativeCoreError(f"native detector rejected telemetry (status={status})")
        return float(score.value), int(worst.value)

    def next_safety_state(
        self,
        current_state: int,
        max_voltage: float,
        max_temperature: float,
        ota_requested: bool,
        reset_requested: bool,
    ) -> int:
        next_state = ctypes.c_int32()
        status = self._lib.bms_v1_next_safety_state(
            current_state,
            max_voltage,
            max_temperature,
            int(ota_requested),
            int(reset_requested),
            ctypes.byref(next_state),
        )
        if status != 0:
            raise NativeCoreError(f"native safety state rejected input (status={status})")
        return int(next_state.value)


FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PackId = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$"),
]
SafetyState = Literal["normal", "isolate_latched", "ota_hold"]
STATE_TO_NATIVE: dict[SafetyState, int] = {"normal": 0, "isolate_latched": 1, "ota_hold": 2}
NATIVE_TO_STATE: dict[int, SafetyState] = {value: key for key, value in STATE_TO_NATIVE.items()}


class Metrics:
    """Small, bounded in-memory Prometheus collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, str], int] = {}
        self._duration: dict[str, float] = {}
        self._detections: dict[str, int] = {"normal": 0, "warn": 0, "critical": 0}

    def request(self, method: str, route: str, status: int, duration: float) -> None:
        status_class = f"{status // 100}xx"
        key = (method, route, status_class)
        with self._lock:
            self._requests[key] = self._requests.get(key, 0) + 1
            self._duration[route] = self._duration.get(route, 0.0) + duration

    def detection(self, severity: str) -> None:
        with self._lock:
            self._detections[severity] += 1

    def render(self) -> str:
        with self._lock:
            lines = [
                "# HELP bms_http_requests_total HTTP requests by bounded route and status class.",
                "# TYPE bms_http_requests_total counter",
            ]
            for (method, route, status_class), count in sorted(self._requests.items()):
                lines.append(
                    f'bms_http_requests_total{{method="{method}",route="{route}",'
                    f'status_class="{status_class}"}} {count}'
                )
            lines.extend(
                [
                    "# HELP bms_http_request_duration_seconds_sum Total request time by bounded route.",
                    "# TYPE bms_http_request_duration_seconds_sum counter",
                ]
            )
            for route, duration in sorted(self._duration.items()):
                lines.append(f'bms_http_request_duration_seconds_sum{{route="{route}"}} {duration:.9f}')
            lines.extend(
                [
                    "# HELP bms_detections_total Detection results by severity.",
                    "# TYPE bms_detections_total counter",
                ]
            )
            for severity, count in sorted(self._detections.items()):
                lines.append(f'bms_detections_total{{severity="{severity}"}} {count}')
            return "\n".join(lines) + "\n"


class TelemetryWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    pack_id: PackId
    timestamp_ms: int = Field(ge=0, strict=True)
    cell_voltages: list[list[FiniteFloat]]
    pack_temp_c: list[FiniteFloat]
    current_safety_state: SafetyState = "normal"
    ota_requested: bool = Field(default=False, strict=True)
    reset_requested: bool = Field(default=False, strict=True)

    @field_validator("cell_voltages")
    @classmethod
    def validate_cells(cls, value: list[list[float]]) -> list[list[float]]:
        if len(value) != SETTINGS.window:
            raise ValueError(f"cell_voltages must contain {SETTINGS.window} steps")
        if any(len(row) != SETTINGS.cells for row in value):
            raise ValueError(f"every step must contain {SETTINGS.cells} cells")
        if any(not 0.0 < cell < 6.0 for row in value for cell in row):
            raise ValueError("cell voltage is outside the measurable range")
        return value

    @field_validator("pack_temp_c")
    @classmethod
    def validate_temperature(cls, value: list[float]) -> list[float]:
        if len(value) != SETTINGS.window:
            raise ValueError(f"pack_temp_c must contain {SETTINGS.window} steps")
        if any(not -80.0 <= temperature <= 150.0 for temperature in value):
            raise ValueError("pack temperature is outside the measurable range")
        return value


class DetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_version: Literal["v1"] = "v1"
    pack_id: str
    timestamp_ms: int
    score: float
    severity: Literal["normal", "warn", "critical"]
    worst_cell: int
    max_cell_voltage: float
    max_pack_temperature: float
    safety_state: SafetyState
    recommended_action: Literal["continue", "halt_balancing", "isolate_cells", "ota_hold"]


core = Core(SETTINGS.core_library)
metrics = Metrics()
app = FastAPI(title="BMS edge anomaly runtime", version="1.1.0")


@app.middleware("http")
async def observe_request(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = secrets.token_hex(8)
    request.state.request_id = request_id
    started = time.perf_counter()
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            response = _problem(400, "Invalid Content-Length", "Content-Length must be an integer.",
                                request.url.path)
        else:
            if declared_length < 0:
                response = _problem(400, "Invalid Content-Length", "Content-Length cannot be negative.",
                                    request.url.path)
            elif declared_length > SETTINGS.max_body_bytes:
                response = _problem(413, "Request body too large",
                                    f"Request body exceeds {SETTINGS.max_body_bytes} bytes.",
                                    request.url.path)
            else:
                response = await call_next(request)
    else:
        response = await call_next(request)
    duration = time.perf_counter() - started
    route_object = request.scope.get("route")
    route = getattr(route_object, "path", "unmatched")
    metrics.request(request.method, route, response.status_code, duration)
    LOGGER.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status": response.status_code,
                "duration_ms": round(duration * 1000, 3),
            },
            separators=(",", ":"),
        )
    )
    response.headers["x-request-id"] = request_id
    return response


def _problem(status: int, title: str, detail: str, instance: str, **extensions: object) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"https://github.com/ndndndn1/bms-edge-anomaly-runtime/problems/{status}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
    }
    body.update(extensions)
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


@app.exception_handler(RequestValidationError)
async def validation_problem(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"location": "/".join(str(part) for part in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return _problem(422, "Request validation failed", "Telemetry did not match the v1 contract.",
                    request.url.path, errors=errors)


@app.exception_handler(NativeCoreError)
async def native_problem(request: Request, exc: NativeCoreError) -> JSONResponse:
    return _problem(503, "Native detector unavailable", str(exc), request.url.path)


@app.exception_handler(HTTPException)
async def http_problem(request: Request, exc: HTTPException) -> JSONResponse:
    return _problem(exc.status_code, "HTTP request failed", str(exc.detail), request.url.path)


@app.get("/health")
def health() -> dict[str, object]:
    """Compatibility aggregate health route. Probes should use /health/live or /health/ready."""
    return readiness()


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def readiness() -> dict[str, object]:
    return {
        "status": "ready",
        "detector": "native-robust-delta",
        "abi_version": "1.0",
        "window": SETTINGS.window,
        "cells": SETTINGS.cells,
        "max_body_bytes": SETTINGS.max_body_bytes,
    }


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return metrics.render()


def _detect(window: TelemetryWindow) -> DetectionResult:
    score, channel = core.score(window.cell_voltages)
    max_voltage = max(max(row) for row in window.cell_voltages)
    max_temperature = max(window.pack_temp_c)
    next_state = core.next_safety_state(
        STATE_TO_NATIVE[window.current_safety_state],
        max_voltage,
        max_temperature,
        window.ota_requested,
        window.reset_requested,
    )
    safety_state = NATIVE_TO_STATE[next_state]
    electrical_trip = safety_state == "isolate_latched"
    if electrical_trip or score >= SETTINGS.critical_score:
        severity, action = "critical", "isolate_cells"
    elif safety_state == "ota_hold":
        severity, action = "normal", "ota_hold"
    elif score >= SETTINGS.warn_score:
        severity, action = "warn", "halt_balancing"
    else:
        severity, action = "normal", "continue"
    metrics.detection(severity)
    return DetectionResult(
        pack_id=window.pack_id,
        timestamp_ms=window.timestamp_ms,
        score=round(score, 4),
        severity=severity,
        worst_cell=channel,
        max_cell_voltage=max_voltage,
        max_pack_temperature=max_temperature,
        safety_state=safety_state,
        recommended_action=action,
    )


@app.post("/v1/detect", response_model=DetectionResult)
def detect_v1(window: TelemetryWindow) -> DetectionResult:
    return _detect(window)


@app.post("/detect", response_model=DetectionResult, deprecated=True)
def detect_compatibility(window: TelemetryWindow) -> DetectionResult:
    """Compatibility route. New clients should use /v1/detect."""
    return _detect(window)
