import json

from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.storage.provider_options import FileProviderOptionsRegistry


def test_provider_options_use_local_icon_paths(tmp_path) -> None:
    client = TestClient(
        create_app(
            provider_options_registry=FileProviderOptionsRegistry(
                tmp_path / "provider_options.json"
            )
        )
    )

    response = client.get("/api/provider-options")

    assert response.status_code == 200
    catalog = {
        provider["provider_id"]: provider
        for provider in response.json()["provider_catalog"]
    }
    assert catalog["gemini"]["logo_url"] == "/provider-icons/gemini.svg"
    assert catalog["deepseek"]["logo_url"] == "/provider-icons/deepseek.png"
    assert catalog["openrouter"]["logo_url"] == "/provider-icons/openrouter.ico"
    assert catalog["glm"]["logo_url"] == "/provider-icons/glm.png"


def test_provider_icon_files_are_served() -> None:
    client = TestClient(create_app())

    expected_content_types = {
        "/provider-icons/gemini.svg": "image/svg+xml",
        "/provider-icons/deepseek.png": "image/png",
        "/provider-icons/openrouter.ico": "image/x-icon",
        "/provider-icons/glm.png": "image/png",
    }
    for path, content_type in expected_content_types.items():
        response = client.get(path)
        assert response.status_code == 200
        assert content_type in response.headers["content-type"]


def test_provider_options_backfill_approval_policy_for_legacy_files(tmp_path) -> None:
    path = tmp_path / "provider_options.json"
    path.write_text(
        json.dumps(
            {
                "default_options": {
                    "conversation_model": {"model": "legacy-conversation"},
                    "utility_model": {"model": "legacy-utility"},
                }
            }
        ),
        encoding="utf-8",
    )

    options = FileProviderOptionsRegistry(path).load()

    assert options["default_options"]["knowledge_approval_policy"] == "agent_decides"
    assert options["default_options"]["conversation_model"]["model"] == "legacy-conversation"
    assert options["default_options"]["conversation_model"]["provider_type"] == "gemini"
