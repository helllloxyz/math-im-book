from __future__ import annotations

import copy
import json
from pathlib import Path


DEFAULT_PROVIDER_OPTIONS = {
    "providers": [
        {
            "provider_type": "gemini",
            "label": "Google Gemini",
            "default_model": "gemini-2.5-flash",
            "models": [
                "gemini-3-flash-preview",
                "gemini-3-pro-preview",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
            ],
            "allow_custom_model": True,
            "requires_base_url": False,
            "default_base_url": None,
        },
        {
            "provider_type": "openai_compatible",
            "label": "OpenAI Compatible",
            "default_model": "deepseek-chat",
            "models": [
                "deepseek-chat",
                "deepseek-reasoner",
            ],
            "allow_custom_model": True,
            "requires_base_url": True,
            "default_base_url": "https://api.openai.com/v1",
        },
    ],
    "provider_catalog": [
        {
            "provider_id": "gemini",
            "provider_type": "gemini",
            "label": "Gemini",
            "default_model": "gemini-2.5-flash",
            "models": [
                "gemini-3-flash-preview",
                "gemini-3-pro-preview",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
            ],
            "allow_custom_model": True,
            "requires_base_url": False,
            "default_base_url": "",
            "logo_url": "/provider-icons/gemini.svg",
        },
        {
            "provider_id": "deepseek",
            "provider_type": "openai_compatible",
            "label": "DeepSeek",
            "default_model": "deepseek-chat",
            "models": [
                "deepseek-chat",
                "deepseek-reasoner",
            ],
            "allow_custom_model": True,
            "requires_base_url": True,
            "default_base_url": "https://api.deepseek.com/v1",
            "logo_url": "/provider-icons/deepseek.png",
        },
        {
            "provider_id": "openrouter",
            "provider_type": "openai_compatible",
            "label": "OpenRouter",
            "default_model": "openrouter/auto",
            "models": [
                "openrouter/auto",
                "openrouter/anthropic/claude-3.7-sonnet",
                "openrouter/google/gemini-2.5-pro",
                "openrouter/openai/gpt-4.1",
            ],
            "allow_custom_model": True,
            "requires_base_url": True,
            "default_base_url": "https://openrouter.ai/api/v1",
            "logo_url": "/provider-icons/openrouter.ico",
        },
        {
            "provider_id": "glm",
            "provider_type": "openai_compatible",
            "label": "GLM",
            "default_model": "glm-4.5-air",
            "models": [
                "glm-4.5",
                "glm-4.5-air",
                "glm-4-air-250414",
                "glm-4-flash",
            ],
            "allow_custom_model": True,
            "requires_base_url": True,
            "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
            "logo_url": "/provider-icons/glm.png",
        },
    ],
    "default_options": {
        "conversation_model": {
            "provider_id": "gemini",
            "provider_type": "gemini",
            "model": "gemini-2.5-flash",
            "credential_id": None,
        },
        "utility_model": {
            "provider_id": "gemini",
            "provider_type": "gemini",
            "model": "gemini-2.5-flash",
            "credential_id": None,
        },
    },
}


class FileProviderOptionsRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, object]:
        if not self.path.exists():
            return copy.deepcopy(DEFAULT_PROVIDER_OPTIONS)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return _normalize_provider_options(payload)

    def save(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=False),
            encoding="utf-8",
        )


def _normalize_provider_options(payload: dict[str, object]) -> dict[str, object]:
    normalized = copy.deepcopy(DEFAULT_PROVIDER_OPTIONS)
    normalized.update(payload)

    catalog_by_id = {
        item["provider_id"]: copy.deepcopy(item)
        for item in normalized.get("provider_catalog", [])
        if isinstance(item, dict) and item.get("provider_id")
    }
    for default_item in DEFAULT_PROVIDER_OPTIONS["provider_catalog"]:
        current = catalog_by_id.get(default_item["provider_id"], {})
        merged = copy.deepcopy(default_item)
        merged.update(current)
        if "models" not in current:
            merged["models"] = copy.deepcopy(default_item["models"])
        catalog_by_id[default_item["provider_id"]] = merged
    normalized["provider_catalog"] = list(catalog_by_id.values())

    if "default_options" not in payload:
        legacy = dict(payload.get("conversation_title_generation") or {})
        normalized["default_options"] = copy.deepcopy(
            DEFAULT_PROVIDER_OPTIONS["default_options"]
        )
        if legacy.get("provider_type") and legacy.get("model"):
            normalized["default_options"]["utility_model"].update(
                {
                    "provider_type": legacy["provider_type"],
                    "model": legacy["model"],
                }
            )
    return normalized
