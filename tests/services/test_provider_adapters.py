from math_im_book.domain.models import ProviderProfile
from math_im_book.services.providers import (
    GeminiAdapter,
    OpenAICompatibleAdapter,
    ProviderRequest,
)
from math_im_book.storage.credentials import CredentialRecord


def test_openai_compatible_adapter_sends_chat_completions_shape() -> None:
    captured: dict[str, object] = {}
    adapter = OpenAICompatibleAdapter(client_factory=_FakeOpenAIClientFactory(captured))
    profile = ProviderProfile(
        provider_type="openai_compatible",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
        credential_id="openai-local",
    )

    result = adapter.generate(
        profile=profile,
        credential=CredentialRecord(credential_id="openai-local", api_key="secret-key"),
        request=ProviderRequest(
            system_instruction="You answer precisely.",
            user_message="Explain linear maps.",
            session_id="chat-1",
        ),
    )

    assert captured["api_key"] == "secret-key"
    assert captured["base_url"] == "https://example.com/v1"
    assert captured["default_headers"] == {
        "X-Target-Base-URL": "https://example.com/v1",
        "X-Session-ID": "chat-1",
    }
    assert captured["model"] == "gpt-4.1-mini"
    assert captured["messages"] == [
        {"role": "system", "content": "You answer precisely."},
        {"role": "user", "content": "Explain linear maps."},
    ]
    assert result.output_text == "Rendered by openai-compatible backend."


def test_gemini_adapter_sends_generate_content_shape() -> None:
    captured: dict[str, object] = {}
    adapter = GeminiAdapter(client_factory=_FakeGeminiClientFactory(captured))
    profile = ProviderProfile(
        provider_type="gemini",
        model="gemini-2.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        credential_id="gemini-local",
    )

    result = adapter.generate(
        profile=profile,
        credential=CredentialRecord(credential_id="gemini-local", api_key="gemini-secret"),
        request=ProviderRequest(
            system_instruction="Use concise math language.",
            user_message="Explain linear maps.",
        ),
    )

    assert captured["api_key"] == "gemini-secret"
    assert captured["http_options"]["base_url"] == "https://generativelanguage.googleapis.com/v1beta"
    assert captured["http_options"]["client_args"]["trust_env"] is True
    assert captured["model"] == "gemini-2.5-flash"
    assert captured["contents"] == "Explain linear maps."
    assert captured["config"]["system_instruction"] == "Use concise math language."
    assert result.output_text == "Rendered by Gemini."


def test_gemini_adapter_streams_generate_content_chunks() -> None:
    captured: dict[str, object] = {}
    adapter = GeminiAdapter(client_factory=_FakeGeminiStreamClientFactory(captured))
    profile = ProviderProfile(
        provider_type="gemini",
        model="gemini-2.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        credential_id="gemini-local",
    )

    chunks = list(
        adapter.generate_stream(
            profile=profile,
            credential=CredentialRecord(credential_id="gemini-local", api_key="gemini-secret"),
            request=ProviderRequest(
                system_instruction="Use concise math language.",
                user_message="Explain linear maps.",
            ),
        )
    )

    assert captured["model"] == "gemini-2.5-flash"
    assert captured["contents"] == "Explain linear maps."
    assert chunks == ["Rendered ", "by Gemini stream."]


def test_openai_compatible_adapter_streams_chunks() -> None:
    captured: dict[str, object] = {}
    adapter = OpenAICompatibleAdapter(client_factory=_FakeOpenAIStreamingClientFactory(captured))
    profile = ProviderProfile(
        provider_type="openai_compatible",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
        credential_id="openai-local",
    )

    chunks = list(
        adapter.generate_stream(
            profile=profile,
            credential=CredentialRecord(credential_id="openai-local", api_key="secret-key"),
            request=ProviderRequest(
                system_instruction="You answer precisely.",
                user_message="Explain linear maps.",
                session_id="chat-1",
                session_id_suffix="utility",
            ),
        )
    )

    assert captured["stream"] is True
    assert captured["default_headers"] == {
        "X-Target-Base-URL": "https://example.com/v1",
        "X-Session-ID": "chat-1:utility",
    }
    assert chunks == ["Rendered ", "by openai stream."]


def test_openai_compatible_adapter_merges_credential_headers_with_runtime_session() -> None:
    captured: dict[str, object] = {}
    adapter = OpenAICompatibleAdapter(client_factory=_FakeOpenAIClientFactory(captured))
    profile = ProviderProfile(
        provider_type="openai_compatible",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
        credential_id="openai-local",
    )

    adapter.generate(
        profile=profile,
        credential=CredentialRecord(
            credential_id="openai-local",
            api_key="secret-key",
            headers={"X-Target-Base-URL": "https://target.example/v1"},
        ),
        request=ProviderRequest(
            system_instruction="You answer precisely.",
            user_message="Explain linear maps.",
            session_id="chat-1",
        ),
    )

    assert captured["default_headers"] == {
        "X-Target-Base-URL": "https://target.example/v1",
        "X-Session-ID": "chat-1",
    }


def test_openai_compatible_adapter_routes_via_local_base_url_env(monkeypatch) -> None:
    captured: dict[str, object] = {}
    adapter = OpenAICompatibleAdapter(client_factory=_FakeOpenAIClientFactory(captured))
    profile = ProviderProfile(
        provider_type="openai_compatible",
        model="gpt-4.1-mini",
        base_url="https://upstream.example/v1",
        credential_id="openai-local",
    )
    monkeypatch.setenv(
        "TRACE_LOCAL_URL",
        "http://localhost:8787/v1",
    )

    adapter.generate(
        profile=profile,
        credential=CredentialRecord(
            credential_id="openai-local",
            api_key="secret-key",
            headers={"X-Target-Base-URL": "https://upstream.example/v1"},
        ),
        request=ProviderRequest(
            system_instruction="You answer precisely.",
            user_message="Explain linear maps.",
            session_id="chat-1",
        ),
    )

    assert captured["base_url"] == "http://localhost:8787/v1"
    assert captured["default_headers"] == {
        "X-Target-Base-URL": "https://upstream.example/v1",
        "X-Session-ID": "chat-1",
    }


class _FakeGeminiClientFactory:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    def __call__(self, *, api_key: str, http_options: object) -> "_FakeGeminiClient":
        self.captured["api_key"] = api_key
        self.captured["http_options"] = _http_options_to_dict(http_options)
        return _FakeGeminiClient(self.captured)


class _FakeGeminiClient:
    def __init__(self, captured: dict[str, object]) -> None:
        self.models = _FakeGeminiModels(captured)


class _FakeGeminiModels:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: object,
    ) -> object:
        self.captured["model"] = model
        self.captured["contents"] = contents
        self.captured["config"] = _generate_config_to_dict(config)
        return _FakeGeminiResponse("Rendered by Gemini.")


class _FakeGeminiStreamClientFactory:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    def __call__(self, *, api_key: str, http_options: object) -> "_FakeGeminiStreamClient":
        self.captured["api_key"] = api_key
        self.captured["http_options"] = _http_options_to_dict(http_options)
        return _FakeGeminiStreamClient(self.captured)


class _FakeGeminiStreamClient:
    def __init__(self, captured: dict[str, object]) -> None:
        self.models = _FakeGeminiStreamModels(captured)


class _FakeGeminiStreamModels:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    def generate_content_stream(
        self,
        *,
        model: str,
        contents: str,
        config: object,
    ) -> object:
        self.captured["model"] = model
        self.captured["contents"] = contents
        self.captured["config"] = _generate_config_to_dict(config)
        return [_FakeGeminiResponse("Rendered "), _FakeGeminiResponse("by Gemini stream.")]


class _FakeGeminiResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeOpenAIClientFactory:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    def __call__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_headers: object = None,
    ) -> "_FakeOpenAIClient":
        self.captured["api_key"] = api_key
        self.captured["base_url"] = base_url
        self.captured["default_headers"] = default_headers
        return _FakeOpenAIClient(self.captured)


class _FakeOpenAIStreamingClientFactory(_FakeOpenAIClientFactory):
    def __call__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_headers: object = None,
    ) -> "_FakeOpenAIStreamingClient":
        self.captured["api_key"] = api_key
        self.captured["base_url"] = base_url
        self.captured["default_headers"] = default_headers
        return _FakeOpenAIStreamingClient(self.captured)


class _FakeOpenAIClient:
    def __init__(self, captured: dict[str, object]) -> None:
        self.chat = _FakeOpenAIChat(captured)


class _FakeOpenAIStreamingClient:
    def __init__(self, captured: dict[str, object]) -> None:
        self.chat = _FakeOpenAIStreamingChat(captured)


class _FakeOpenAIChat:
    def __init__(self, captured: dict[str, object]) -> None:
        self.completions = _FakeOpenAICompletions(captured)


class _FakeOpenAIStreamingChat:
    def __init__(self, captured: dict[str, object]) -> None:
        self.completions = _FakeOpenAIStreamingCompletions(captured)


class _FakeOpenAICompletions:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    def create(self, *, model: str, messages: list[dict[str, str]]) -> object:
        self.captured["model"] = model
        self.captured["messages"] = messages
        return _FakeOpenAIResponse("Rendered by openai-compatible backend.")


class _FakeOpenAIStreamingCompletions:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        stream: bool,
    ) -> object:
        self.captured["model"] = model
        self.captured["messages"] = messages
        self.captured["stream"] = stream
        return [_FakeOpenAIChunk("Rendered "), _FakeOpenAIChunk("by openai stream.")]


class _FakeOpenAIResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeOpenAIChoice(content)]


class _FakeOpenAIChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeOpenAIMessage(content)


class _FakeOpenAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeOpenAIChunk:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeOpenAIChunkChoice(content)]


class _FakeOpenAIChunkChoice:
    def __init__(self, content: str) -> None:
        self.delta = _FakeOpenAIDelta(content)


class _FakeOpenAIDelta:
    def __init__(self, content: str) -> None:
        self.content = content


def _http_options_to_dict(http_options: object) -> dict[str, object]:
    if hasattr(http_options, "model_dump"):
        return http_options.model_dump(exclude_none=True)
    return dict(http_options)


def _generate_config_to_dict(config: object) -> dict[str, object]:
    if hasattr(config, "model_dump"):
        return config.model_dump(exclude_none=True)
    return dict(config)
