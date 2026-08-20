from __future__ import annotations

import os
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Iterator

from math_im_book.domain.models import ProviderProfile, ProviderResult
from math_im_book.services.runtime_logging import get_runtime_logger, safe_log_value
from math_im_book.storage.credentials import CredentialRecord, FileCredentialRegistry


logger = get_runtime_logger("providers")


@dataclass(slots=True)
class ProviderRequest:
    system_instruction: str
    user_message: str
    session_id: str | None = None
    session_id_suffix: str | None = None
    purpose: str = "answer"


class ProviderError(Exception):
    pass


class ProviderAuthenticationError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass


class ProviderUpstreamError(ProviderError):
    pass


class UnsupportedProviderError(ProviderError):
    pass


class OpenAICompatibleAdapter:
    _LOCAL_BASE_URL_ENV = "TRACE_LOCAL_URL"

    def __init__(
        self,
        client_factory: Callable[..., object] | None = None,
    ) -> None:
        self.client_factory = client_factory

    def generate(
        self,
        profile: ProviderProfile,
        credential: CredentialRecord,
        request: ProviderRequest,
    ) -> ProviderResult:
        try:
            client_factory = self.client_factory
            if client_factory is None:
                openai = _load_openai_sdk()
                client_factory = openai.OpenAI
            target_base_url = (profile.base_url or "https://api.openai.com/v1").rstrip(
                "/"
            )
            client = client_factory(
                api_key=credential.api_key,
                base_url=self._resolved_base_url(target_base_url),
                default_headers=self._default_headers(
                    credential,
                    request,
                    target_base_url=target_base_url,
                ),
            )
            response = client.chat.completions.create(
                model=profile.model,
                messages=[
                    {"role": "system", "content": request.system_instruction},
                    {"role": "user", "content": request.user_message},
                ],
            )
        except Exception as exc:
            mapped_error = _map_openai_sdk_error(exc)
            if mapped_error is not None:
                raise mapped_error from exc
            raise

        output_text = ""
        if response.choices:
            message = response.choices[0].message
            if isinstance(message.content, str):
                output_text = message.content
        return ProviderResult(
            output_text=output_text,
            provider_name="openai_compatible",
        )

    def generate_stream(
        self,
        profile: ProviderProfile,
        credential: CredentialRecord,
        request: ProviderRequest,
    ) -> Iterator[str]:
        try:
            client_factory = self.client_factory
            if client_factory is None:
                openai = _load_openai_sdk()
                client_factory = openai.OpenAI
            target_base_url = (profile.base_url or "https://api.openai.com/v1").rstrip(
                "/"
            )
            client = client_factory(
                api_key=credential.api_key,
                base_url=self._resolved_base_url(target_base_url),
                default_headers=self._default_headers(
                    credential,
                    request,
                    target_base_url=target_base_url,
                ),
            )
            stream = client.chat.completions.create(
                model=profile.model,
                messages=[
                    {"role": "system", "content": request.system_instruction},
                    {"role": "user", "content": request.user_message},
                ],
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            mapped_error = _map_openai_sdk_error(exc)
            if mapped_error is not None:
                raise mapped_error from exc
            raise

    @staticmethod
    def _default_headers(
        credential: CredentialRecord,
        request: ProviderRequest,
        *,
        target_base_url: str,
    ) -> dict[str, str] | None:
        headers = dict(credential.headers)
        # When routing requests through a local proxy, let it know where to forward.
        headers.setdefault("X-Target-Base-URL", target_base_url)
        session_id = request.session_id
        if session_id:
            if request.session_id_suffix:
                session_id = f"{session_id}:{request.session_id_suffix}"
            headers["X-Session-ID"] = session_id
        return headers or None

    @classmethod
    def _resolved_base_url(cls, target_base_url: str) -> str:
        local_base_url = (os.getenv(cls._LOCAL_BASE_URL_ENV) or "").strip().rstrip("/")
        return local_base_url or target_base_url


class GeminiAdapter:
    def __init__(
        self,
        client_factory: Callable[..., object] | None = None,
    ) -> None:
        self.client_factory = client_factory

    def generate(
        self,
        profile: ProviderProfile,
        credential: CredentialRecord,
        request: ProviderRequest,
    ) -> ProviderResult:
        genai, genai_errors, genai_types = _load_google_genai()
        client_factory = self.client_factory or genai.Client
        client = client_factory(
            api_key=credential.api_key,
            http_options=self._build_http_options(profile, credential),
        )
        try:
            response = client.models.generate_content(
                model=profile.model,
                contents=request.user_message,
                config=genai_types.GenerateContentConfig(
                    system_instruction=request.system_instruction
                ),
            )
        except genai_errors.ClientError as exc:
            raise _map_gemini_sdk_error(exc) from exc
        except genai_errors.ServerError as exc:
            raise ProviderUpstreamError(_format_gemini_sdk_error(exc)) from exc
        return ProviderResult(
            output_text=response.text or "",
            provider_name="gemini",
        )

    def generate_stream(
        self,
        profile: ProviderProfile,
        credential: CredentialRecord,
        request: ProviderRequest,
    ) -> Iterator[str]:
        genai, genai_errors, genai_types = _load_google_genai()
        client_factory = self.client_factory or genai.Client
        client = client_factory(
            api_key=credential.api_key,
            http_options=self._build_http_options(profile, credential),
        )
        try:
            stream = client.models.generate_content_stream(
                model=profile.model,
                contents=request.user_message,
                config=genai_types.GenerateContentConfig(
                    system_instruction=request.system_instruction
                ),
            )
            for chunk in stream:
                text = chunk.text or ""
                if text:
                    yield text
        except genai_errors.ClientError as exc:
            raise _map_gemini_sdk_error(exc) from exc
        except genai_errors.ServerError as exc:
            raise ProviderUpstreamError(_format_gemini_sdk_error(exc)) from exc

    @staticmethod
    def _build_http_options(
        profile: ProviderProfile,
        credential: CredentialRecord,
    ) -> Any:
        _, _, genai_types = _load_google_genai()
        headers = credential.headers or None
        base_url = profile.base_url.rstrip("/") if profile.base_url else None
        return genai_types.HttpOptions(
            base_url=base_url,
            headers=headers,
            client_args={"trust_env": True},
        )


class ProviderGateway:
    def __init__(
        self,
        credential_registry: FileCredentialRegistry,
        openai_adapter: OpenAICompatibleAdapter | None = None,
        gemini_adapter: GeminiAdapter | None = None,
    ) -> None:
        self.credential_registry = credential_registry
        self.openai_adapter = openai_adapter or OpenAICompatibleAdapter()
        self.gemini_adapter = gemini_adapter or GeminiAdapter()

    def generate(
        self,
        profile: ProviderProfile,
        request: ProviderRequest,
    ) -> ProviderResult:
        started_at = perf_counter()
        self._log_started(profile, request, stream=False)
        try:
            credential = self.credential_registry.get(profile.credential_id)
            if profile.provider_type == "gemini":
                result = self.gemini_adapter.generate(profile, credential, request)
            elif profile.provider_type == "openai_compatible":
                result = self.openai_adapter.generate(profile, credential, request)
            else:
                raise UnsupportedProviderError(
                    f"Unsupported provider_type: {profile.provider_type}"
                )
        except Exception as exc:
            self._log_failed(profile, request, started_at, exc, stream=False)
            raise
        logger.info(
            "Model call completed: purpose=%s provider=%s model=%s session=%s "
            "duration_ms=%d output_chars=%d",
            safe_log_value(request.purpose),
            safe_log_value(profile.provider_type),
            safe_log_value(profile.model),
            safe_log_value(request.session_id),
            self._duration_ms(started_at),
            len(result.output_text),
        )
        return result

    def generate_stream(
        self,
        profile: ProviderProfile,
        request: ProviderRequest,
    ) -> Iterator[str]:
        started_at = perf_counter()
        self._log_started(profile, request, stream=True)
        try:
            credential = self.credential_registry.get(profile.credential_id)
            if profile.provider_type == "gemini":
                stream = self.gemini_adapter.generate_stream(profile, credential, request)
            elif profile.provider_type == "openai_compatible":
                stream = self.openai_adapter.generate_stream(profile, credential, request)
            else:
                raise UnsupportedProviderError(
                    f"Unsupported provider_type: {profile.provider_type}"
                )
        except Exception as exc:
            self._log_failed(profile, request, started_at, exc, stream=True)
            raise

        def logged_stream() -> Iterator[str]:
            chunk_count = 0
            output_chars = 0
            try:
                for chunk in stream:
                    chunk_count += 1
                    output_chars += len(chunk)
                    yield chunk
            except Exception as exc:
                self._log_failed(profile, request, started_at, exc, stream=True)
                raise
            logger.info(
                "Model stream completed: purpose=%s provider=%s model=%s session=%s "
                "duration_ms=%d chunks=%d output_chars=%d",
                safe_log_value(request.purpose),
                safe_log_value(profile.provider_type),
                safe_log_value(profile.model),
                safe_log_value(request.session_id),
                self._duration_ms(started_at),
                chunk_count,
                output_chars,
            )

        return logged_stream()

    @staticmethod
    def _log_started(
        profile: ProviderProfile,
        request: ProviderRequest,
        *,
        stream: bool,
    ) -> None:
        logger.info(
            "Model %s started: purpose=%s provider=%s model=%s session=%s",
            "stream" if stream else "call",
            safe_log_value(request.purpose),
            safe_log_value(profile.provider_type),
            safe_log_value(profile.model),
            safe_log_value(request.session_id),
        )

    @classmethod
    def _log_failed(
        cls,
        profile: ProviderProfile,
        request: ProviderRequest,
        started_at: float,
        exc: Exception,
        *,
        stream: bool,
    ) -> None:
        logger.warning(
            "Model %s failed: purpose=%s provider=%s model=%s session=%s "
            "duration_ms=%d error=%s detail=%s",
            "stream" if stream else "call",
            safe_log_value(request.purpose),
            safe_log_value(profile.provider_type),
            safe_log_value(profile.model),
            safe_log_value(request.session_id),
            cls._duration_ms(started_at),
            type(exc).__name__,
            safe_log_value(exc),
        )

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((perf_counter() - started_at) * 1000)


class FakeProviderGateway:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result

    def generate(
        self,
        profile: ProviderProfile,
        request: ProviderRequest,
    ) -> ProviderResult:
        if "context planner" in request.system_instruction:
            return ProviderResult(
                output_text=_fake_planner_output(request.user_message),
                provider_name=self.result.provider_name,
            )
        return self.result

    def generate_stream(
        self,
        profile: ProviderProfile,
        request: ProviderRequest,
    ) -> Iterator[str]:
        yield self.result.output_text


def _fake_planner_output(user_message: str) -> str:
    question_match = re.search(r"^Question: (.*)$", user_message, flags=re.MULTILINE)
    question = question_match.group(1) if question_match else ""
    candidates = [
        (match.group(1), match.group(2))
        for match in re.finditer(
            r"^- id=([^;]+); title=([^;]+);",
            user_message,
            flags=re.MULTILINE,
        )
    ]
    question_lower = question.lower()
    for node_id, title in candidates:
        title_lower = title.lower()
        id_words = node_id.replace("-", " ").lower()
        if title_lower in question_lower or id_words in question_lower:
            return (
                '{"action_type":"reuse_answer",'
                f'"selected_node_ids":["{node_id}"],'
                '"draft_requests":[],'
                '"user_visible_reason":"The selected node directly matches the question."}'
            )
    selected_node_ids = f'["{candidates[0][0]}"]' if candidates else "[]"
    title = _fake_draft_title(question)
    return (
        '{"action_type":"expand_with_drafts",'
        f'"selected_node_ids":{selected_node_ids},'
        f'"draft_requests":[{{"title":"{title}",'
        '"draft_type":"missing_definition",'
        '"reason":"The knowledge base is missing this definition."}],'
        '"user_visible_reason":"Existing knowledge is insufficient."}'
    )


def _fake_draft_title(question: str) -> str:
    cleaned = question.strip().rstrip("?.! ")
    cleaned = re.sub(r"^explain\s+(what\s+)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^what\s+is\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+is$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(a|an|the)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.title() or "Generated Node"


def _map_gemini_sdk_error(exc: Any) -> ProviderError:
    if exc.code in {401, 403}:
        return ProviderAuthenticationError(_format_gemini_sdk_error(exc))
    if exc.code == 429:
        return ProviderRateLimitError(_format_gemini_sdk_error(exc))
    return ProviderUpstreamError(_format_gemini_sdk_error(exc))


def _format_gemini_sdk_error(exc: Any) -> str:
    message = exc.message or str(exc)
    return f"gemini provider returned HTTP {exc.code}: {message}"


def _load_google_genai() -> tuple[Any, Any, Any]:
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types as genai_types

    return genai, genai_errors, genai_types


def _load_openai_sdk() -> Any:
    import openai

    return openai


def _map_openai_sdk_error(exc: Exception) -> ProviderError | None:
    status_code = getattr(exc, "status_code", None)
    if not isinstance(status_code, int):
        return None
    message = f"openai_compatible provider returned HTTP {status_code}"
    if status_code in {401, 403}:
        return ProviderAuthenticationError(message)
    if status_code == 429:
        return ProviderRateLimitError(message)
    if status_code >= 500:
        return ProviderUpstreamError(message)
    return ProviderUpstreamError(message)
