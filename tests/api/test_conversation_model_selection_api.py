import json

from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import ProviderResult
from math_im_book.services.providers import FakeProviderGateway
from math_im_book.storage.credentials import FileCredentialRegistry
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.provider_options import FileProviderOptionsRegistry
from math_im_book.storage.sessions import FileSessionStore


def test_ask_defaults_to_configured_conversation_model_and_persists_selection(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "credential_id": "deepseek",
                        "provider_id": "deepseek",
                        "provider_type": "openai_compatible",
                        "api_key": "secret",
                        "base_url": "https://api.deepseek.com/v1",
                        "headers": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    options_path = tmp_path / "provider_options.json"
    options_path.write_text(
        json.dumps(
            {
                "providers": [],
                "provider_catalog": [
                    {
                        "provider_id": "deepseek",
                        "provider_type": "openai_compatible",
                        "label": "DeepSeek",
                        "default_model": "deepseek-chat",
                        "models": ["deepseek-chat"],
                        "allow_custom_model": True,
                        "requires_base_url": True,
                        "default_base_url": "https://api.deepseek.com/v1",
                        "logo_url": None,
                    }
                ],
                "default_options": {
                    "conversation_model": {
                        "provider_id": "deepseek",
                        "provider_type": "openai_compatible",
                        "credential_id": "deepseek",
                        "model": "deepseek-chat",
                    },
                    "utility_model": {
                        "provider_id": "deepseek",
                        "provider_type": "openai_compatible",
                        "credential_id": "deepseek",
                        "model": "deepseek-chat",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(
        create_app(
            repository=MarkdownKnowledgeRepository(tmp_path / "knowledge"),
            credential_registry=FileCredentialRegistry(credentials_path),
            provider_options_registry=FileProviderOptionsRegistry(options_path),
            session_store=FileSessionStore(tmp_path / "sessions"),
            provider_gateway=FakeProviderGateway(
                ProviderResult(output_text="ok", provider_name="openai_compatible")
            ),
        )
    )

    response = client.post("/api/ask", json={"question": "ping"})

    assert response.status_code == 200
    body = response.json()
    session_id = body["session"]["session_id"]
    assert body["session"]["provider_profile"]["provider_type"] == "openai_compatible"
    assert body["session"]["provider_profile"]["model"] == "deepseek-chat"
    assert body["session"]["provider_profile"]["credential_id"] == "deepseek"
    assert body["session"]["conversation_model"] == {
        "provider_id": "deepseek",
        "provider_type": "openai_compatible",
        "credential_id": "deepseek",
        "model": "deepseek-chat",
    }

    followup = client.post(
        "/api/ask",
        json={
            "question": "ping again",
            "session_id": session_id,
        },
    )

    assert followup.status_code == 200
    followup_body = followup.json()
    assert followup_body["session"]["conversation_model"] == body["session"][
        "conversation_model"
    ]


def test_patch_session_updates_conversation_model_selection(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "credential_id": "deepseek",
                        "provider_id": "deepseek",
                        "provider_type": "openai_compatible",
                        "api_key": "secret",
                        "base_url": "https://api.deepseek.com/v1",
                        "headers": {},
                    },
                    {
                        "credential_id": "gemini",
                        "provider_id": "gemini",
                        "provider_type": "gemini",
                        "api_key": "secret",
                        "base_url": None,
                        "headers": {},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    options_path = tmp_path / "provider_options.json"
    options_path.write_text(
        json.dumps(
            {
                "providers": [],
                "provider_catalog": [
                    {
                        "provider_id": "deepseek",
                        "provider_type": "openai_compatible",
                        "label": "DeepSeek",
                        "default_model": "deepseek-chat",
                        "models": ["deepseek-chat"],
                        "allow_custom_model": True,
                        "requires_base_url": True,
                        "default_base_url": "https://api.deepseek.com/v1",
                        "logo_url": None,
                    },
                    {
                        "provider_id": "gemini",
                        "provider_type": "gemini",
                        "label": "Gemini",
                        "default_model": "gemini-2.5-flash",
                        "models": ["gemini-2.5-flash"],
                        "allow_custom_model": False,
                        "requires_base_url": False,
                        "default_base_url": "",
                        "logo_url": None,
                    },
                ],
                "default_options": {
                    "conversation_model": {
                        "provider_id": "deepseek",
                        "provider_type": "openai_compatible",
                        "credential_id": "deepseek",
                        "model": "deepseek-chat",
                    },
                    "utility_model": {
                        "provider_id": "deepseek",
                        "provider_type": "openai_compatible",
                        "credential_id": "deepseek",
                        "model": "deepseek-chat",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(
        create_app(
            repository=MarkdownKnowledgeRepository(tmp_path / "knowledge"),
            credential_registry=FileCredentialRegistry(credentials_path),
            provider_options_registry=FileProviderOptionsRegistry(options_path),
            session_store=FileSessionStore(tmp_path / "sessions"),
            provider_gateway=FakeProviderGateway(
                ProviderResult(output_text="ok", provider_name="openai_compatible")
            ),
        )
    )

    created = client.post("/api/ask", json={"question": "ping"})
    session_id = created.json()["session"]["session_id"]

    updated = client.patch(
        f"/api/sessions/{session_id}",
        json={
            "conversation_model": {
                "provider_id": "gemini",
                "provider_type": "gemini",
                "credential_id": "gemini",
                "model": "gemini-2.5-flash",
            }
        },
    )

    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["conversation_model"]["provider_id"] == "gemini"
    assert updated_body["provider_profile"]["provider_type"] == "gemini"
