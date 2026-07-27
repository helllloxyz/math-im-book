from __future__ import annotations

from pathlib import Path


def default_user_profile_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data/config/USER.md"


class FileUserProfileRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_user_profile_path()

    def load(self) -> str:
        if not self.path.exists():
            return ""
        try:
            return self.path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError, ValueError):
            return ""
