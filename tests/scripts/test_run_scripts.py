from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("script_name", ["run.sh", "run.bat"])
def test_user_launcher_uses_concise_server_logging(script_name: str) -> None:
    script = (REPO_ROOT / "scripts" / script_name).read_text(encoding="utf-8")

    assert "--log-level warning" in script
    assert "--no-access-log" in script
