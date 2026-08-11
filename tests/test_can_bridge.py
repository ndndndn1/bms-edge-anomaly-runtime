import json
import struct
from pathlib import Path

import pytest

from src.can_bridge import CanFrame, TelemetryCollector, decode_socketcan_frame, reference_frames


PROFILE = Path("config/reference-can-profile.json")


def test_reference_profile_is_deterministic_and_complete() -> None:
    profile = json.loads(PROFILE.read_text())
    frames = list(reference_frames(profile))
    assert len(frames) == 32 * 5
    collector = TelemetryCollector("reference-pack", 8, 32, 1700000000000)
    outputs = [output for frame in frames if (output := collector.ingest(frame)) is not None]
    assert len(outputs) == 1
    assert outputs[0]["timestamp_ms"] == 1700000000000
    assert outputs[0]["cell_voltages"][-1][3] == pytest.approx(4.0061)


def test_socketcan_classic_frame_decode() -> None:
    raw = struct.pack("=IB3x8s", 0x180, 4, bytes.fromhex("9088911600000000"))
    assert decode_socketcan_frame(raw) == CanFrame(0x180, bytes.fromhex("90889116"))


def test_socketcan_fd_frame_decode() -> None:
    raw = struct.pack("=IBB2x64s", 0x190, 12, 0, bytes(range(64)))
    assert decode_socketcan_frame(raw) == CanFrame(0x190, bytes(range(12)))


def test_incomplete_step_is_discarded_at_temperature_boundary() -> None:
    collector = TelemetryCollector("pack", 2, 3, 1)
    assert collector.ingest(CanFrame(0x190, bytes.fromhex("0bb8"))) is None


def test_invalid_socketcan_length_rejected() -> None:
    with pytest.raises(ValueError):
        decode_socketcan_frame(bytes(8))
