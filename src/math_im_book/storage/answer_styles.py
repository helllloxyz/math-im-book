from __future__ import annotations

import copy
import json
from pathlib import Path

from math_im_book.domain.models import AnswerStyle, AnswerStyleCatalog


DEFAULT_ANSWER_STYLE_INDEX = {
    "default_style_id": "default",
    "styles": [
        {
            "style_id": "default",
            "label": "Default",
            "description": "Legacy default style placeholder.",
        },
        {
            "style_id": "concise",
            "label": "Concise",
            "description": "Short answers that stay complete.",
        },
        {
            "style_id": "step-by-step",
            "label": "Step by Step",
            "description": "Numbered solutions with explicit intermediate steps.",
        },
        {
            "style_id": "intuitive",
            "label": "Intuitive",
            "description": "Lead with intuition, examples, and high-level structure.",
        },
        {
            "style_id": "rigorous",
            "label": "Rigorous",
            "description": "Prioritize precise definitions and careful derivations.",
        },
    ],
}

DEFAULT_ANSWER_STYLE_MARKDOWN = {
    "default": """# Default

- Legacy compatibility style entry.
- Use the standard session guidance with no extra per-question override.
""",
    "concise": """# Concise

- Keep answers short and complete.
- Prefer the smallest useful amount of explanation.
- Skip extended derivations unless they are needed.
""",
    "step-by-step": """# Step by Step

- Break solutions into numbered steps.
- Show each important transformation explicitly.
- Finish with the final result after the derivation.
""",
    "intuitive": """# Intuitive

- Start with the main idea before the formal details.
- Use examples, analogies, and geometric intuition when helpful.
- Keep the explanation approachable without losing correctness.
""",
    "rigorous": """# Rigorous

- State assumptions and definitions explicitly.
- Keep derivations precise and logically complete.
- Avoid skipping steps that matter to correctness.
""",
}


class FileAnswerStyleRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self) -> AnswerStyleCatalog:
        if not self._index_path.exists():
            return _default_answer_style_catalog()

        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return _default_answer_style_catalog()

        if not isinstance(payload, dict):
            return _default_answer_style_catalog()

        default_style_id = str(
            payload.get("default_style_id")
            or DEFAULT_ANSWER_STYLE_INDEX["default_style_id"]
        ).strip()
        styles: list[AnswerStyle] = []
        for item in payload.get("styles", []):
            if not isinstance(item, dict):
                continue
            style_id = str(item.get("style_id") or "").strip()
            label = str(item.get("label") or style_id).strip()
            if not style_id or not label:
                continue
            if style_id not in DEFAULT_ANSWER_STYLE_MARKDOWN:
                continue
            instructions = self._read_instructions(style_id)
            styles.append(
                AnswerStyle(
                    style_id=style_id,
                    label=label,
                    description=item.get("description"),
                    instructions=instructions,
                    is_default=style_id == default_style_id,
                )
            )

        if not styles:
            return _default_answer_style_catalog()
        return AnswerStyleCatalog(
            default_style_id=default_style_id,
            styles=styles,
        )

    def get(self, style_id: str) -> AnswerStyle:
        return self.load().get(style_id)

    @property
    def _index_path(self) -> Path:
        return self.root / "index.json"

    def _read_instructions(self, style_id: str) -> str:
        path = self.root / f"{style_id}.md"
        if not path.exists():
            return DEFAULT_ANSWER_STYLE_MARKDOWN.get(style_id, "").strip()
        return path.read_text(encoding="utf-8").strip()


def _default_answer_style_catalog() -> AnswerStyleCatalog:
    return AnswerStyleCatalog(
        default_style_id=DEFAULT_ANSWER_STYLE_INDEX["default_style_id"],
        styles=[
            AnswerStyle(
                style_id=item["style_id"],
                label=item["label"],
                description=item.get("description"),
                instructions=DEFAULT_ANSWER_STYLE_MARKDOWN[item["style_id"]].strip(),
                is_default=item["style_id"] == DEFAULT_ANSWER_STYLE_INDEX["default_style_id"],
            )
            for item in copy.deepcopy(DEFAULT_ANSWER_STYLE_INDEX["styles"])
        ],
    )
