from __future__ import annotations

import copy
import json
from pathlib import Path

from math_im_book.domain.models import StrategyAgent, StrategyAgentCatalog


DEFAULT_STRATEGY_AGENT_INDEX = {
    "default_strategy_agent_id": "top-down",
    "agents": [
        {
            "strategy_agent_id": "top-down",
            "label": "Top Down",
            "description": "Start from the high-level structure.",
        },
        {
            "strategy_agent_id": "raw",
            "label": "Raw",
            "description": "Use the raw question text with minimal shaping.",
        },
    ],
}

DEFAULT_STRATEGY_AGENT_MARKDOWN = {
    "top-down": """# Top Down

- Start with the high-level structure.
- Move from the broad idea to the details.
- Reframe the problem before diving into derivations.
""",
    "raw": """# Raw

- Use the user's question as-is.
- Keep the framing close to the original wording.
- Avoid adding structure unless it helps clarity.
""",
}


class FileStrategyAgentRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self) -> StrategyAgentCatalog:
        if not self._index_path.exists():
            return _default_strategy_agent_catalog()

        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return _default_strategy_agent_catalog()

        if not isinstance(payload, dict):
            return _default_strategy_agent_catalog()

        default_strategy_agent_id = str(
            payload.get("default_strategy_agent_id") or ""
        ).strip()
        agents: list[StrategyAgent] = []
        for item in payload.get("agents", []):
            if not isinstance(item, dict):
                continue
            strategy_agent_id = str(item.get("strategy_agent_id") or "").strip()
            label = str(item.get("label") or strategy_agent_id).strip()
            if not strategy_agent_id or not label:
                continue
            instructions = self._read_instructions(strategy_agent_id)
            agents.append(
                StrategyAgent(
                    strategy_agent_id=strategy_agent_id,
                    label=label,
                    description=item.get("description"),
                    instructions=instructions,
                    is_default=strategy_agent_id == default_strategy_agent_id,
                )
            )

        if not agents:
            return _default_strategy_agent_catalog()

        if default_strategy_agent_id not in {
            agent.strategy_agent_id for agent in agents
        }:
            default_strategy_agent_id = agents[0].strategy_agent_id

        for agent in agents:
            agent.is_default = agent.strategy_agent_id == default_strategy_agent_id

        return StrategyAgentCatalog(
            default_strategy_agent_id=default_strategy_agent_id,
            agents=agents,
        )

    def get(self, strategy_agent_id: str) -> StrategyAgent:
        return self.load().get(strategy_agent_id)

    @property
    def _index_path(self) -> Path:
        return self.root / "index.json"

    def _read_instructions(self, strategy_agent_id: str) -> str:
        path = self.root / f"{strategy_agent_id}.md"
        if not path.exists():
            return DEFAULT_STRATEGY_AGENT_MARKDOWN.get(strategy_agent_id, "").strip()
        try:
            return path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError, ValueError):
            return DEFAULT_STRATEGY_AGENT_MARKDOWN.get(strategy_agent_id, "").strip()


def _default_strategy_agent_catalog() -> StrategyAgentCatalog:
    return StrategyAgentCatalog(
        default_strategy_agent_id=DEFAULT_STRATEGY_AGENT_INDEX[
            "default_strategy_agent_id"
        ],
        agents=[
            StrategyAgent(
                strategy_agent_id=item["strategy_agent_id"],
                label=item["label"],
                description=item.get("description"),
                instructions=DEFAULT_STRATEGY_AGENT_MARKDOWN[
                    item["strategy_agent_id"]
                ].strip(),
                is_default=item["strategy_agent_id"]
                == DEFAULT_STRATEGY_AGENT_INDEX["default_strategy_agent_id"],
            )
            for item in copy.deepcopy(DEFAULT_STRATEGY_AGENT_INDEX["agents"])
        ],
    )
