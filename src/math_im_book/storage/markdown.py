from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from math_im_book.domain.models import KnowledgeNode, NodeReference


class MarkdownKnowledgeRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._node_list_cache: list[KnowledgeNode] | None = None
        self._incoming_reference_index_cache: dict[str, list[NodeReference]] | None = None
        self._cache_signature: tuple[tuple[str, int, int], ...] | None = None

    def save_node(self, node: KnowledgeNode) -> Path:
        path = self.root / f"{node.id}.md"
        updated_at = node.updated_at or datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        metadata = {
            "id": node.id,
            "title": node.title,
            "type": node.type,
            "summary": node.summary,
            "parent_id": node.parent_id,
            "source": node.source,
            "symbols": node.symbols,
            "symbol_scopes": node.symbol_scopes,
            "references": [
                {"node_id": ref.node_id, "reason": ref.reason}
                for ref in node.references
            ],
            "status": node.status,
            "revision": max(1, node.revision),
            "updated_at": updated_at,
        }
        content = "---\n"
        content += yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
        content += "---\n"
        content += node.detail
        path.write_text(content, encoding="utf-8")
        self._invalidate_caches()
        return path

    def get_node(self, node_id: str) -> KnowledgeNode:
        path = self.root / f"{node_id}.md"
        raw = path.read_text(encoding="utf-8")
        metadata_text, detail = self._split_front_matter(raw)
        metadata = yaml.safe_load(metadata_text)
        return KnowledgeNode(
            id=metadata["id"],
            title=metadata["title"],
            type=metadata["type"],
            summary=metadata["summary"],
            detail=detail,
            parent_id=metadata.get("parent_id"),
            source=metadata["source"],
            references=[
                NodeReference(
                    node_id=ref["node_id"],
                    reason=ref["reason"],
                )
                for ref in metadata.get("references", [])
            ],
            status=metadata.get("status", "ready"),
            symbols=metadata.get("symbols", {}),
            symbol_scopes=metadata.get("symbol_scopes", {}),
            revision=max(1, int(metadata.get("revision", 1))),
            updated_at=metadata.get("updated_at"),
        )

    def list_nodes(self) -> list[KnowledgeNode]:
        self._refresh_caches_if_stale()
        return self._snapshot_node_list()

    def list_incoming_references(self, node_id: str) -> list[NodeReference]:
        self._refresh_caches_if_stale()
        if self._incoming_reference_index_cache is None:
            incoming_reference_index: dict[str, list[NodeReference]] = {}
            for source_node in self._snapshot_node_list():
                for reference in source_node.references:
                    incoming_reference_index.setdefault(reference.node_id, []).append(
                        NodeReference(
                            node_id=source_node.id,
                            reason=reference.reason,
                        )
                    )
            for references in incoming_reference_index.values():
                references.sort(key=lambda reference: (reference.node_id, reference.reason))
            self._incoming_reference_index_cache = incoming_reference_index

        return list(self._incoming_reference_index_cache.get(node_id, []))

    def list_related_node_ids(self, node_id: str) -> list[str]:
        node = self.get_node(node_id)
        direct_node_ids = sorted(
            {
                reference.node_id
                for reference in node.references
                if reference.node_id != node_id
            }
        )
        incoming_node_ids = [
            reference.node_id
            for reference in self.list_incoming_references(node_id)
            if reference.node_id != node_id and reference.node_id not in direct_node_ids
        ]
        return [*direct_node_ids, *incoming_node_ids]

    def list_related_session_ids(self, node_id: str) -> list[str]:
        node = self.get_node(node_id)
        related_session_ids: list[str] = [node.source]

        for direct_node_id in sorted(
            {
                reference.node_id
                for reference in node.references
                if reference.node_id != node_id
            }
        ):
            try:
                related_session_ids.append(self.get_node(direct_node_id).source)
            except FileNotFoundError:
                continue

        for reference in self.list_incoming_references(node_id):
            if reference.node_id == node_id:
                continue
            try:
                related_session_ids.append(self.get_node(reference.node_id).source)
            except FileNotFoundError:
                continue

        return self._dedupe_preserving_order(related_session_ids)

    def _snapshot_node_list(self) -> list[KnowledgeNode]:
        if self._node_list_cache is None:
            nodes = [self.get_node(path.stem) for path in sorted(self.root.glob("*.md"))]
            self._node_list_cache = sorted(nodes, key=lambda node: node.id)
        return list(self._node_list_cache)

    def _invalidate_caches(self) -> None:
        self._node_list_cache = None
        self._incoming_reference_index_cache = None
        self._cache_signature = None

    def _refresh_caches_if_stale(self) -> None:
        current_signature = self._current_signature()
        if current_signature != self._cache_signature:
            self._invalidate_caches()
            self._cache_signature = current_signature

    def _current_signature(self) -> tuple[tuple[str, int, int], ...]:
        signature: list[tuple[str, int, int]] = []
        for path in sorted(self.root.glob("*.md")):
            stat_result = path.stat()
            signature.append((path.name, stat_result.st_mtime_ns, stat_result.st_size))
        return tuple(signature)

    @staticmethod
    def _dedupe_preserving_order(items: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    @staticmethod
    def _split_front_matter(raw: str) -> tuple[str, str]:
        _, metadata_text, detail = raw.split("---\n", maxsplit=2)
        return metadata_text, detail
