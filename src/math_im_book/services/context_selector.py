from __future__ import annotations

import re
from collections.abc import Callable

from math_im_book.domain.models import SessionBranchContext
from math_im_book.services.symbols import SymbolRegistry
from math_im_book.storage.markdown import MarkdownKnowledgeRepository


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+|[\u3400-\u9fff]+")
MAX_ACTIVE_NODES = 6
MAX_SUMMARY_NODES = 8
STOPWORDS = {
    "a",
    "an",
    "and",
    "does",
    "for",
    "from",
    "how",
    "into",
    "its",
    "maps",
    "that",
    "the",
    "this",
    "what",
    "when",
    "with",
}


class ContextSelector:
    def __init__(
        self,
        repository: MarkdownKnowledgeRepository,
        scope_node_ids_resolver: Callable[[str], list[str]] | None = None,
    ) -> None:
        self.repository = repository
        self.scope_node_ids_resolver = scope_node_ids_resolver

    def select(
        self,
        question: str,
        branch_context: SessionBranchContext,
    ) -> SessionBranchContext:
        allowed_node_ids = self._allowed_node_ids(branch_context.knowledge_scope_id)
        anchor_id = (
            branch_context.fork_anchor.node_id
            if branch_context.fork_anchor is not None
            else None
        )
        active_node_ids: list[str] = []
        seen_node_ids: set[str] = set()
        summary_node_ids: list[str] = []
        seen_summary_node_ids: set[str] = set()
        for node_id in branch_context.summary_node_ids:
            if allowed_node_ids is not None and node_id not in allowed_node_ids:
                continue
            if node_id in seen_summary_node_ids:
                continue
            seen_summary_node_ids.add(node_id)
            summary_node_ids.append(node_id)

        if anchor_id is not None and (
            allowed_node_ids is None or anchor_id in allowed_node_ids
        ):
            seen_node_ids.add(anchor_id)
            active_node_ids.append(anchor_id)
            for node_id in self.repository.list_related_node_ids(anchor_id):
                if allowed_node_ids is not None and node_id not in allowed_node_ids:
                    continue
                if node_id in seen_node_ids:
                    continue
                seen_node_ids.add(node_id)
                active_node_ids.append(node_id)
        elif branch_context.active_node_ids:
            for node_id in branch_context.active_node_ids:
                if allowed_node_ids is not None and node_id not in allowed_node_ids:
                    continue
                if node_id in seen_node_ids:
                    continue
                seen_node_ids.add(node_id)
                active_node_ids.append(node_id)

        lexical_matches = self._lexical_matches(
            question,
            seen_node_ids,
            allowed_node_ids=allowed_node_ids,
        )
        if active_node_ids:
            for node_id, score in lexical_matches:
                if score >= 2:
                    seen_summary_node_ids.discard(node_id)
                    seen_node_ids.add(node_id)
                    if len(active_node_ids) < MAX_ACTIVE_NODES:
                        active_node_ids.append(node_id)
                elif node_id not in seen_summary_node_ids:
                    seen_summary_node_ids.add(node_id)
                    if len(summary_node_ids) < MAX_SUMMARY_NODES:
                        summary_node_ids.append(node_id)
        else:
            for node_id, score in lexical_matches:
                if score >= 2:
                    seen_summary_node_ids.discard(node_id)
                    seen_node_ids.add(node_id)
                    if len(active_node_ids) < MAX_ACTIVE_NODES:
                        active_node_ids.append(node_id)
                elif node_id not in seen_summary_node_ids:
                    seen_summary_node_ids.add(node_id)
                    if len(summary_node_ids) < MAX_SUMMARY_NODES:
                        summary_node_ids.append(node_id)
        active_node_ids = active_node_ids[:MAX_ACTIVE_NODES]
        summary_node_ids = summary_node_ids[:MAX_SUMMARY_NODES]
        summary_node_ids = [
            node_id for node_id in summary_node_ids if node_id not in seen_node_ids
        ]

        return SessionBranchContext(
            branch_id=branch_context.branch_id,
            parent_session_id=branch_context.parent_session_id,
            root_session_id=branch_context.root_session_id,
            focus_question=branch_context.focus_question,
            fork_anchor=branch_context.fork_anchor,
            active_node_ids=active_node_ids,
            summary_node_ids=summary_node_ids,
            active_symbols=(
                self._active_symbols(active_node_ids, branch_context.active_symbols)
                if active_node_ids
                else (
                    {}
                    if branch_context.knowledge_scope_id is not None
                    else dict(branch_context.active_symbols)
                )
            ),
            knowledge_scope_id=branch_context.knowledge_scope_id,
        )

    def _lexical_matches(
        self,
        question: str,
        excluded_node_ids: set[str],
        *,
        allowed_node_ids: set[str] | None = None,
    ) -> list[tuple[str, int]]:
        question_tokens = _tokenize(question)
        scored_nodes: list[tuple[str, int]] = []
        for node in self.repository.list_nodes():
            if node.id in excluded_node_ids:
                continue
            if allowed_node_ids is not None and node.id not in allowed_node_ids:
                continue
            score = len(question_tokens & _tokenize(f"{node.title} {node.summary}"))
            if score <= 0:
                continue
            scored_nodes.append((node.id, score))
        scored_nodes.sort(key=lambda item: (-item[1], item[0]))
        return scored_nodes

    def _allowed_node_ids(self, scope_id: str | None) -> set[str] | None:
        if scope_id is None or self.scope_node_ids_resolver is None:
            return None
        try:
            return set(self.scope_node_ids_resolver(scope_id))
        except KeyError:
            return set()

    def _active_symbols(
        self,
        active_node_ids: list[str],
        branch_symbols: dict[str, str],
    ) -> dict[str, str]:
        nodes = [self.repository.get_node(node_id) for node_id in active_node_ids]
        return SymbolRegistry().build_context(
            nodes,
            branch_symbols=branch_symbols,
        ).symbols


def _tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in TOKEN_PATTERN.findall(text.lower()):
        token = raw.strip()
        if not token:
            continue
        if re.fullmatch(r"[\u3400-\u9fff]+", token):
            if len(token) <= 2:
                tokens.add(token)
            else:
                tokens.add(token)
                tokens.update(token[index : index + 2] for index in range(len(token) - 1))
            continue
        if len(token) >= 3 and token not in STOPWORDS:
            tokens.add(token)
    return tokens
