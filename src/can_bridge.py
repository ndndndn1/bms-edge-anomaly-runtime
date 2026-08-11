"""Receive-only Linux SocketCAN bridge for the reference BMS CAN profile."""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

CELL_BASE_ID = 0x180
TEMPERATURE_ID = 0x190
CAN_EFF_MASK = 0x1FFFFFFF
CAN_RAW_FD_FRAMES = 5


@dataclass(frozen=True)
class CanFrame:
    arbitration_id: int
    data: bytes


class TelemetryCollector:
    def __init__(self, pack_id: str, cells: int, window: int, timestamp_ms: int | None = None):
        if cells < 1 or cells % 2 != 0:
            raise ValueError("reference CAN profile requires a positive, even cell count")
        if window < 3:
            raise ValueError("window must contain at least three steps")
        self.pack_id = pack_id
        self.cells = cells
        self.window = window
        self.timestamp_ms = timestamp_ms
        self._pairs: dict[int, tuple[float, float]] = {}
        self._voltages: list[list[float]] = []
        self._temperatures: list[float] = []

    def ingest(self, frame: CanFrame) -> dict[str, object] | None:
        pair = frame.arbitration_id - CELL_BASE_ID
        if 0 <= pair < self.cells // 2 and len(frame.data) >= 4:
            first, second = struct.unpack(">HH", frame.data[:4])
            self._pairs[pair] = (first / 10_000.0, second / 10_000.0)
            return None
        if frame.arbitration_id != TEMPERATURE_ID or len(frame.data) < 2:
            return None
        if len(self._pairs) != self.cells // 2:
            self._pairs.clear()
            return None

        raw_temperature = struct.unpack(">h", frame.data[:2])[0]
        row = [value for pair_index in range(self.cells // 2) for value in self._pairs[pair_index]]
        self._pairs.clear()
        self._voltages.append(row)
        self._temperatures.append(raw_temperature / 100.0)
        if len(self._voltages) < self.window:
            return None

        result: dict[str, object] = {
            "pack_id": self.pack_id,
            "timestamp_ms": self.timestamp_ms or int(time.time() * 1000),
            "cell_voltages": self._voltages,
            "pack_temp_c": self._temperatures,
        }
        self._voltages = []
        self._temperatures = []
        return result


def decode_socketcan_frame(frame: bytes) -> CanFrame:
    if len(frame) not in (16, 72):
        raise ValueError(f"unexpected SocketCAN frame size: {len(frame)}")
    arbitration_id = struct.unpack_from("=I", frame)[0] & CAN_EFF_MASK
    payload_length = frame[4]
    maximum = 8 if len(frame) == 16 else 64
    if payload_length > maximum:
        raise ValueError("SocketCAN payload length exceeds frame capacity")
    return CanFrame(arbitration_id, frame[8 : 8 + payload_length])


def reference_frames(profile: dict[str, object]) -> Iterator[CanFrame]:
    cells = int(profile["cells"])
    window = int(profile["window"])
    baseline = [float(value) for value in profile["baseline_volts"]]  # type: ignore[arg-type]
    if len(baseline) != cells or cells % 2:
        raise ValueError("baseline_volts must match an even cell count")
    drift = float(profile.get("drift_volts_per_step", 0.0))
    anomaly_step = int(profile.get("anomaly_step", -1))
    anomaly_cell = int(profile.get("anomaly_cell", -1))
    anomaly_delta = float(profile.get("anomaly_delta_volts", 0.0))
    temperature = float(profile["temperature_c"])
    for step in range(window):
        row = [value + step * drift for value in baseline]
        if step == anomaly_step and 0 <= anomaly_cell < cells:
            row[anomaly_cell] += anomaly_delta
        for pair in range(cells // 2):
            encoded = struct.pack(">HH", round(row[pair * 2] * 10_000),
                                  round(row[pair * 2 + 1] * 10_000)) + bytes(4)
            yield CanFrame(CELL_BASE_ID + pair, encoded)
        yield CanFrame(TEMPERATURE_ID, struct.pack(">h", round(temperature * 100)) + bytes(6))


def submit(endpoint: str, payload: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def run_mock(path: Path, endpoint: str | None) -> None:
    profile = json.loads(path.read_text())
    collector = TelemetryCollector(
        str(profile["pack_id"]), int(profile["cells"]), int(profile["window"]),
        int(profile["timestamp_ms"]),
    )
    payload = None
    for frame in reference_frames(profile):
        payload = collector.ingest(frame) or payload
    if payload is None:
        raise RuntimeError("reference profile did not produce a complete telemetry window")
    output = submit(endpoint, payload) if endpoint else payload
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))


def run_socketcan(interface: str, endpoint: str, pack_id: str, cells: int, window: int) -> None:
    # SOCK_RAW is opened receive-only by design: this module contains no send call.
    with socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as can_socket:
        can_socket.setsockopt(socket.SOL_CAN_RAW, CAN_RAW_FD_FRAMES, 1)
        can_socket.bind((interface,))
        collector = TelemetryCollector(pack_id, cells, window)
        while True:
            payload = collector.ingest(decode_socketcan_frame(can_socket.recv(72)))
            if payload is not None:
                print(json.dumps(submit(endpoint, payload), sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--interface", help="SocketCAN interface, for example can0 or vcan0")
    source.add_argument("--mock", type=Path, help="deterministic reference profile JSON")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8801/v1/detect")
    parser.add_argument("--no-submit", action="store_true", help="print mock telemetry without HTTP")
    parser.add_argument("--pack-id", default="socketcan-pack")
    parser.add_argument("--cells", type=int, default=8)
    parser.add_argument("--window", type=int, default=32)
    args = parser.parse_args()
    if args.mock:
        run_mock(args.mock, None if args.no_submit else args.endpoint)
    elif args.no_submit:
        parser.error("--no-submit is supported only with --mock")
    else:
        run_socketcan(args.interface, args.endpoint, args.pack_id, args.cells, args.window)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"can bridge failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
