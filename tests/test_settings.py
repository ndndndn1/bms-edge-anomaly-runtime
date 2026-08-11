import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("BMS_WINDOW", "2", "BMS_WINDOW must be between"),
        ("BMS_WARN_SCORE", "nan", "BMS_WARN_SCORE must be finite"),
        ("BMS_CRITICAL_SCORE", "7", "BMS_WARN_SCORE must be lower"),
    ],
)
def test_invalid_startup_configuration_fails_closed(name: str, value: str, message: str) -> None:
    environment = os.environ.copy()
    environment[name] = value
    result = subprocess.run(
        [sys.executable, "-c", "import src.main"],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert message in result.stderr
