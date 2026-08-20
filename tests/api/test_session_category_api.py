import json

from fastapi.testclient import TestClient

from math_im_book.api.app import _parse_session_identity, create_app
from math_im_book.domain.models import ProviderResult
from math_im_book.services.providers import FakeProviderGateway, ProviderRequest
from math_im_book.storage.credentials import FileCredentialRegistry
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.provider_options import FileProviderOptionsRegistry
from math_im_book.storage.sessions import FileSessionStore


class CategoryAwareFakeProviderGateway(FakeProviderGateway):
    def generate(self, profile, request: ProviderRequest) -> ProviderResult:
        if request.session_id_suffix == "utility":
            return ProviderResult(
                output_text=(
                    '{"title":"Symmetry Through Group Actions",'
                    '"category":"group-theory"}'
                ),
                provider_name="openai_compatible",
            )
        return super().generate(profile, request)


def _configured_client(tmp_path) -> tuple[TestClient, FileSessionStore]:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "credential_id": "utility",
                        "provider_id": "utility",
                        "provider_type": "openai_compatible",
                        "api_key": "secret",
                        "base_url": "https://example.com/v1",
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
                        "provider_id": "utility",
                        "provider_type": "openai_compatible",
                        "label": "Utility",
                        "default_model": "utility-model",
                        "models": ["utility-model"],
                        "allow_custom_model": False,
                        "requires_base_url": True,
                        "default_base_url": "https://example.com/v1",
                        "logo_url": None,
                    }
                ],
                "default_options": {
                    "conversation_model": {
                        "provider_id": "utility",
                        "provider_type": "openai_compatible",
                        "credential_id": "utility",
                        "model": "utility-model",
                    },
                    "utility_model": {
                        "provider_id": "utility",
                        "provider_type": "openai_compatible",
                        "credential_id": "utility",
                        "model": "utility-model",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    session_store = FileSessionStore(tmp_path / "sessions")
    gateway = CategoryAwareFakeProviderGateway(
        ProviderResult(output_text="A group action describes a symmetry.", provider_name="fake")
    )
    return (
        TestClient(
            create_app(
                repository=MarkdownKnowledgeRepository(tmp_path / "knowledge"),
                credential_registry=FileCredentialRegistry(credentials_path),
                provider_options_registry=FileProviderOptionsRegistry(options_path),
                session_store=session_store,
                provider_gateway=gateway,
            )
        ),
        session_store,
    )


def test_first_answer_persists_model_generated_title_and_category(tmp_path) -> None:
    client, session_store = _configured_client(tmp_path)

    response = client.post("/api/ask", json={"question": "How do group actions encode symmetry?"})

    assert response.status_code == 200
    session = response.json()["session"]
    assert session["title"] == "Symmetry Through Group Actions"
    assert session["icon"] == "group-theory"
    stored = session_store.load_record(session["session_id"])
    assert stored is not None
    assert stored.icon == "group-theory"


def test_session_identity_parser_accepts_json_fences_and_rejects_unknown_categories() -> None:
    assert _parse_session_identity(
        '```json\n{"title":"Prime Patterns!","category":"number-theory"}\n```'
    ) == ("Prime Patterns", "number-theory")
    assert _parse_session_identity(
        '{"title":"Prime Patterns","category":"mathematics"}'
    ) is None


def test_manual_category_override_is_preserved_on_followup(tmp_path) -> None:
    client, _ = _configured_client(tmp_path)
    created = client.post(
        "/api/ask",
        json={"question": "How do group actions encode symmetry?"},
    ).json()["session"]

    updated = client.patch(
        f'/api/sessions/{created["session_id"]}',
        json={"icon": "topology"},
    )
    followup = client.post(
        "/api/ask",
        json={
            "question": "Can you give another example?",
            "session_id": created["session_id"],
        },
    )

    assert updated.status_code == 200
    assert updated.json()["icon"] == "topology"
    assert followup.status_code == 200
    assert followup.json()["session"]["icon"] == "topology"
