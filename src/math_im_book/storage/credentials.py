from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CredentialRecord:
    credential_id: str
    api_key: str
    headers: dict[str, str] = field(default_factory=dict)


class FileCredentialRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, credential_id: str) -> CredentialRecord:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        for item in payload.get("credentials", []):
            if item["credential_id"] == credential_id:
                return CredentialRecord(
                    credential_id=item["credential_id"],
                    api_key=item["api_key"],
                    headers=item.get("headers", {}),
                )
        raise KeyError(f"Unknown credential_id: {credential_id}")
