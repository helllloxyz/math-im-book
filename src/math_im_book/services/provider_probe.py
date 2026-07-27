from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx

from math_im_book.domain.models import ProviderProfile
from math_im_book.services.providers import (
    GeminiAdapter,
    OpenAICompatibleAdapter,
    ProviderAuthenticationError,
    ProviderRequest,
    ProviderUpstreamError,
)
from math_im_book.storage.credentials import CredentialRecord

DEFAULT_MODELS = {
    "gemini": "gemini-3-flash-preview",
    "openai_compatible": "gpt-4.1-mini",
}


class ProbeStatus(str, Enum):
    OK = "ok"
    TIMEOUT = "timeout"
    AUTH_ERROR = "auth_error"
    UPSTREAM_ERROR = "upstream_error"
    CONFIG_ERROR = "config_error"


@dataclass(slots=True)
class ProbeResult:
    status: ProbeStatus
    message: str
    provider_name: str
    model: str
    credential_id: str
    output_preview: str = ""


def build_profile_from_credentials(
    credentials_path: Path,
    credential_id: str | None = None,
    model: str | None = None,
) -> ProviderProfile:
    payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    credential_payload = _select_credential_payload(payload, credential_id)
    provider_type = credential_payload.get("provider_type", "gemini")
    resolved_model = model or credential_payload.get("default_model")
    if not resolved_model:
        resolved_model = DEFAULT_MODELS.get(provider_type)
    if not resolved_model:
        raise ValueError(f"No default model configured for provider_type={provider_type}")
    return ProviderProfile(
        provider_type=provider_type,
        model=resolved_model,
        credential_id=credential_payload["credential_id"],
        base_url=credential_payload.get("base_url"),
    )


def build_credential_record(
    credentials_path: Path,
    credential_id: str,
) -> CredentialRecord:
    payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    credential_payload = _select_credential_payload(payload, credential_id)
    return CredentialRecord(
        credential_id=credential_payload["credential_id"],
        api_key=credential_payload["api_key"],
        headers=credential_payload.get("headers", {}),
    )


def run_provider_probe(
    profile: ProviderProfile,
    credential: CredentialRecord,
    timeout_seconds: float,
    http_client: httpx.Client | None = None,
    system_instruction: str = "Reply with a short connectivity confirmation.",
    user_message: str = "Return exactly: GEMINI_OK",
) -> ProbeResult:
    client = http_client or httpx.Client(timeout=timeout_seconds, trust_env=False)
    close_client = http_client is None
    try:
        request = ProviderRequest(
            system_instruction=system_instruction,
            user_message=user_message,
        )
        if profile.provider_type == "gemini":
            provider_result = GeminiAdapter(
                client_factory=_build_gemini_client_factory(
                    timeout_seconds=timeout_seconds,
                    http_client=http_client,
                )
            ).generate(
                profile=profile,
                credential=credential,
                request=request,
            )
        elif profile.provider_type == "openai_compatible":
            provider_result = OpenAICompatibleAdapter(http_client=client).generate(
                profile=profile,
                credential=credential,
                request=request,
            )
        else:
            return ProbeResult(
                status=ProbeStatus.CONFIG_ERROR,
                message=f"Unsupported provider_type: {profile.provider_type}",
                provider_name=profile.provider_type,
                model=profile.model,
                credential_id=profile.credential_id,
            )
        return ProbeResult(
            status=ProbeStatus.OK,
            message="Provider request completed successfully.",
            provider_name=provider_result.provider_name,
            model=profile.model,
            credential_id=profile.credential_id,
            output_preview=provider_result.output_text[:200],
        )
    except httpx.TimeoutException as exc:
        return ProbeResult(
            status=ProbeStatus.TIMEOUT,
            message=str(exc) or "Provider request timed out.",
            provider_name=profile.provider_type,
            model=profile.model,
            credential_id=profile.credential_id,
        )
    except ProviderAuthenticationError as exc:
        return ProbeResult(
            status=ProbeStatus.AUTH_ERROR,
            message=str(exc),
            provider_name=profile.provider_type,
            model=profile.model,
            credential_id=profile.credential_id,
        )
    except (ProviderUpstreamError, httpx.HTTPError) as exc:
        return ProbeResult(
            status=ProbeStatus.UPSTREAM_ERROR,
            message=str(exc),
            provider_name=profile.provider_type,
            model=profile.model,
            credential_id=profile.credential_id,
        )
    finally:
        if close_client:
            client.close()


def build_probe_http_client(
    timeout_seconds: float,
    ipv4_only: bool = False,
    trust_env: bool = True,
) -> httpx.Client:
    timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds)
    if not ipv4_only:
        return httpx.Client(
            timeout=timeout,
            trust_env=trust_env,
        )
    transport = httpx.HTTPTransport(
        retries=0,
        local_address="0.0.0.0",
    )
    return httpx.Client(
        timeout=timeout,
        trust_env=trust_env,
        transport=transport,
    )


def _build_gemini_client_factory(
    timeout_seconds: float,
    http_client: httpx.Client | None,
):
    def factory(*, api_key: str, http_options: object):
        from google import genai

        options = http_options
        if http_client is not None and hasattr(options, "httpx_client"):
            options.httpx_client = http_client
        if hasattr(options, "timeout") and options.timeout is None:
            options.timeout = int(timeout_seconds * 1000)
        return genai.Client(api_key=api_key, http_options=options)

    return factory


def _select_credential_payload(
    payload: dict[str, object],
    credential_id: str | None,
) -> dict[str, object]:
    credentials = payload.get("credentials", [])
    if not isinstance(credentials, list):
        raise ValueError("credentials payload must contain a list")

    if credential_id is not None:
        for item in credentials:
            if item.get("credential_id") == credential_id:
                return item
        raise ValueError(f"Unknown credential_id: {credential_id}")

    for item in credentials:
        if item.get("provider_type", "gemini") == "gemini":
            return item
    if credentials:
        return credentials[0]
    raise ValueError("No credentials found in credentials file")
