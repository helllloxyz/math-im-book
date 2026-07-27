import json

from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.storage.credentials import FileCredentialRegistry


def test_update_credential_writes_exact_model_list_to_file(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "credential_id": "gemini",
                        "api_key": "sk-existing",
                        "provider_type": "gemini",
                        "provider_id": "gemini",
                        "headers": {},
                        "base_url": None,
                        "default_model": "gemini-3-flash-preview",
                        "models": [
                            "gemini-3-flash-preview",
                            "gemini-3-pro-preview",
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(
        create_app(credential_registry=FileCredentialRegistry(credentials_path))
    )

    response = client.put(
        "/api/credentials/gemini",
        json={
            "provider_type": "gemini",
            "provider_id": "gemini",
            "default_model": "gemini-3-flash-preview",
            "models": ["gemini-3-flash-preview"],
            "headers": {},
        },
    )

    assert response.status_code == 200
    assert response.json()["credential"]["models"] == ["gemini-3-flash-preview"]
    payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    assert payload["credentials"] == [
        {
            "credential_id": "gemini",
            "api_key": "sk-existing",
            "provider_type": "gemini",
            "provider_id": "gemini",
            "headers": {},
            "base_url": None,
            "default_model": "gemini-3-flash-preview",
            "models": ["gemini-3-flash-preview"],
        }
    ]
