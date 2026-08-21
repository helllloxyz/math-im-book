from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock, Thread
from time import perf_counter
from typing import Callable
from uuid import uuid4

from math_im_book.domain.models import (
    AnswerAnchor,
    KnowledgeNode,
    NodeReference,
    PendingDraftRequest,
    ProviderProfile,
)
from math_im_book.services.concurrency import (
    OrderedConcurrentRunner,
    ThreadPoolOrderedConcurrentRunner,
)
from math_im_book.services.providers import ProviderGateway, ProviderRequest
from math_im_book.services.runtime_logging import get_runtime_logger, safe_log_value
from math_im_book.storage.explorer import ExplorerStore
from math_im_book.storage.markdown import MarkdownKnowledgeRepository


logger = get_runtime_logger("knowledge_jobs")


@dataclass(frozen=True, slots=True)
class _DraftCompileTask:
    anchor: AnswerAnchor
    title: str
    draft_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class _DraftCompileResult:
    anchor: AnswerAnchor
    title: str
    node: KnowledgeNode | None = None
    error_message: str | None = None


@dataclass(slots=True)
class KnowledgeJobRecord:
    job_id: str
    status: str
    session_id: str | None = None
    selection_source_text: str = ""
    anchors: list[AnswerAnchor] = field(default_factory=list)
    question: str = ""
    selected_node_ids: list[str] = field(default_factory=list)
    draft_requests: list[PendingDraftRequest] = field(default_factory=list)
    provider_profile: ProviderProfile | None = None
    source_message_id: str | None = None
    error_message: str | None = None
    symbol_constraints: dict[str, str] = field(default_factory=dict)
    symbol_conflicts: list[str] = field(default_factory=list)


class InMemoryKnowledgeJobRepository:
    def __init__(
        self,
        repository: MarkdownKnowledgeRepository,
        provider_gateway: ProviderGateway | None = None,
        *,
        auto_start: bool = True,
        concurrent_runner: OrderedConcurrentRunner | None = None,
        explorer_store: ExplorerStore | None = None,
    ) -> None:
        self.repository = repository
        self.provider_gateway = provider_gateway
        self.auto_start = auto_start
        self.concurrent_runner = concurrent_runner or ThreadPoolOrderedConcurrentRunner()
        self.explorer_store = explorer_store
        self._jobs: dict[str, KnowledgeJobRecord] = {}
        self._terminal_listeners: list[Callable[[KnowledgeJobRecord], None]] = []
        self._lock = Lock()

    def add_terminal_listener(
        self,
        listener: Callable[[KnowledgeJobRecord], None],
    ) -> None:
        with self._lock:
            self._terminal_listeners.append(listener)

    def submit_compile_job(
        self,
        *,
        session_id: str | None = None,
        question: str,
        anchors: list[AnswerAnchor],
        selected_node_ids: list[str],
        draft_requests: list[PendingDraftRequest],
        selection_source_text: str = "",
        provider_profile: ProviderProfile | None = None,
        source_message_id: str | None = None,
        symbol_constraints: dict[str, str] | None = None,
        symbol_conflicts: list[str] | None = None,
    ) -> KnowledgeJobRecord:
        job = KnowledgeJobRecord(
            job_id=f"job-{uuid4().hex[:8]}",
            status="queued",
            session_id=session_id,
            selection_source_text=selection_source_text,
            anchors=copy.deepcopy(anchors),
            question=question,
            selected_node_ids=list(selected_node_ids),
            draft_requests=list(draft_requests),
            provider_profile=provider_profile,
            source_message_id=source_message_id,
            symbol_constraints=dict(symbol_constraints or {}),
            symbol_conflicts=list(symbol_conflicts or []),
        )
        with self._lock:
            self._jobs[job.job_id] = job
        logger.info(
            "Knowledge job queued: job=%s session=%s drafts=%d selected_nodes=%d",
            job.job_id,
            safe_log_value(job.session_id),
            len(job.draft_requests) or 1,
            len(job.selected_node_ids),
        )
        if self.auto_start:
            Thread(target=self._run_job, args=(job.job_id,), daemon=True).start()
        return self.get_job(job.job_id) or job

    def get_job(self, job_id: str) -> KnowledgeJobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job is not None else None

    def list_jobs(self, session_id: str | None = None) -> list[KnowledgeJobRecord]:
        with self._lock:
            jobs = list(self._jobs.values())
        if session_id is not None:
            jobs = [job for job in jobs if job.session_id == session_id]
        return [copy.deepcopy(job) for job in jobs]

    def attach_source_message(
        self,
        job_id: str,
        *,
        session_id: str,
        source_message_id: str,
    ) -> None:
        should_notify = False
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            job.session_id = session_id
            job.source_message_id = source_message_id
            should_notify = job.status in {"completed", "failed"}
        if should_notify:
            self._notify_terminal_listeners(job_id)

    def run_job(self, job_id: str) -> KnowledgeJobRecord:
        self._run_job(job_id)
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def _run_job(self, job_id: str) -> None:
        started_at = perf_counter()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "running"
            session_id = job.session_id
        logger.info(
            "Knowledge job started: job=%s session=%s",
            job_id,
            safe_log_value(session_id),
        )
        try:
            self._compile_job(job_id)
        except Exception as exc:  # pragma: no cover - defensive guard
            with self._lock:
                job = self._jobs.get(job_id)
                if job is not None:
                    job.status = "failed"
                    job.error_message = str(exc)
                    job.anchors = [
                        AnswerAnchor(
                            anchor_id=anchor.anchor_id,
                            label=anchor.label,
                            status="failed",
                            node_id=None,
                        )
                        for anchor in job.anchors
                    ]
        snapshot = self.get_job(job_id)
        if snapshot is not None and snapshot.status == "completed":
            logger.info(
                "Knowledge job completed: job=%s session=%s duration_ms=%d nodes=%d",
                job_id,
                safe_log_value(snapshot.session_id),
                round((perf_counter() - started_at) * 1000),
                sum(anchor.node_id is not None for anchor in snapshot.anchors),
            )
        elif snapshot is not None:
            logger.warning(
                "Knowledge job failed: job=%s session=%s duration_ms=%d detail=%s",
                job_id,
                safe_log_value(snapshot.session_id),
                round((perf_counter() - started_at) * 1000),
                safe_log_value(snapshot.error_message),
            )
        self._notify_terminal_listeners(job_id)

    def _notify_terminal_listeners(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status not in {"completed", "failed"}:
                return
            snapshot = copy.deepcopy(job)
            listeners = list(self._terminal_listeners)
        for listener in listeners:
            try:
                listener(snapshot)
            except Exception:
                # A failed observer must not change the result of a completed compile.
                logger.exception(
                    "Knowledge job observer failed: job=%s listener=%s",
                    job_id,
                    safe_log_value(
                        getattr(listener, "__name__", type(listener).__name__)
                    ),
                )
                continue

    def _compile_job(self, job_id: str) -> None:
        job = self._get_job_or_raise(job_id)
        drafts = list(job.draft_requests) or [
            PendingDraftRequest(
                title=job.question,
                draft_type="summary",
                reason="Compile the conversation into reusable knowledge.",
            )
        ]
        anchors = list(job.anchors) or [
            AnswerAnchor(
                anchor_id=self._slugify(draft.title),
                label=draft.title,
                status="pending",
            )
            for draft in drafts
        ]
        anchor_nodes = self._load_anchor_nodes(job.selected_node_ids)
        updated_anchors: list[AnswerAnchor] = []
        errors: list[str] = []
        compile_tasks: list[_DraftCompileTask] = []
        for index, draft in enumerate(drafts):
            anchor = anchors[index] if index < len(anchors) else AnswerAnchor(
                anchor_id=self._slugify(draft.title),
                label=draft.title,
                status="pending",
            )
            title = draft.title.strip() or "Compiled Knowledge"
            compile_tasks.append(
                _DraftCompileTask(
                    anchor=anchor,
                    title=title,
                    draft_type=draft.draft_type,
                    reason=draft.reason,
                )
            )

        compile_results = self.concurrent_runner.run_ordered(
            compile_tasks,
            lambda task: self._compile_draft_task(task, job, anchor_nodes, len(drafts)),
        )
        for result in compile_results:
            if result.error_message is not None:
                errors.append(result.error_message)
                updated_anchors.append(
                    AnswerAnchor(
                        anchor_id=result.anchor.anchor_id,
                        label=result.anchor.label,
                        status="failed",
                        node_id=None,
                    )
                )
                continue
            if result.node is None:
                errors.append("Knowledge compile did not return a node")
                updated_anchors.append(
                    AnswerAnchor(
                        anchor_id=result.anchor.anchor_id,
                        label=result.anchor.label,
                        status="failed",
                        node_id=None,
                    )
                )
                continue
            try:
                try:
                    existing_node = self.repository.get_node(result.node.id)
                except FileNotFoundError:
                    existing_node = None
                result.node.revision = (
                    existing_node.revision + 1 if existing_node is not None else 1
                )
                result.node.updated_at = datetime.now(timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                )
                self.repository.save_node(result.node)
                if self.explorer_store is not None:
                    self.explorer_store.ensure_item_location(
                        item_type="knowledge_node",
                        item_id=result.node.id,
                        location_source="system",
                    )
            except Exception as exc:
                errors.append(
                    str(exc) if len(drafts) == 1 else f"{result.title}: {exc}"
                )
                updated_anchors.append(
                    AnswerAnchor(
                        anchor_id=result.anchor.anchor_id,
                        label=result.anchor.label,
                        status="failed",
                        node_id=None,
                    )
                )
                continue
            updated_anchors.append(
                AnswerAnchor(
                    anchor_id=result.anchor.anchor_id,
                    label=result.anchor.label,
                    status="ready",
                    node_id=result.node.id,
                )
            )
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                return
            current.status = "failed" if errors else "completed"
            current.error_message = "; ".join(errors) if errors else None
            current.anchors = updated_anchors

    def _compile_draft_task(
        self,
        task: _DraftCompileTask,
        job: KnowledgeJobRecord,
        anchor_nodes: list[KnowledgeNode],
        draft_count: int,
    ) -> _DraftCompileResult:
        try:
            node = self._compile_draft_node(
                task.title,
                task.draft_type,
                task.reason,
                job,
                anchor_nodes,
            )
        except Exception as exc:
            error_message = str(exc) if draft_count == 1 else f"{task.title}: {exc}"
            return _DraftCompileResult(
                anchor=task.anchor,
                title=task.title,
                error_message=error_message,
            )
        return _DraftCompileResult(
            anchor=task.anchor,
            title=task.title,
            node=node,
        )

    def _compile_draft_node(
        self,
        title: str,
        draft_type: str,
        reason: str,
        job: KnowledgeJobRecord,
        anchor_nodes: list[KnowledgeNode],
    ) -> KnowledgeNode:
        summary, detail = self._compiled_content(
            title,
            draft_type,
            reason,
            job,
            anchor_nodes,
        )
        references = [
            NodeReference(
                node_id=node.id,
                reason=f"Knowledge anchor for {title}",
            )
            for node in anchor_nodes
        ]
        return KnowledgeNode(
            id=self._slugify(title),
            title=title,
            type=draft_type,
            summary=summary,
            detail=detail,
            parent_id=anchor_nodes[0].parent_id if anchor_nodes else None,
            source=job.session_id or "chat:auto",
            references=references,
            status="ready",
            symbols=self._merge_symbols(anchor_nodes, job.symbol_constraints),
        )

    def _get_job_or_raise(self, job_id: str) -> KnowledgeJobRecord:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return job

    def _load_anchor_nodes(self, anchor_ids: list[str]) -> list[KnowledgeNode]:
        nodes: list[KnowledgeNode] = []
        for node_id in anchor_ids:
            try:
                nodes.append(self.repository.get_node(node_id))
            except FileNotFoundError:
                continue
        return nodes

    def _compiled_content(
        self,
        title: str,
        draft_type: str,
        reason: str,
        job: KnowledgeJobRecord,
        anchor_nodes: list[KnowledgeNode],
    ) -> tuple[str, str]:
        if self.provider_gateway is None or job.provider_profile is None:
            raise ValueError(
                "Knowledge compile requires a provider profile and provider gateway"
            )
        provider_output = self.provider_gateway.generate(
            job.provider_profile,
            ProviderRequest(
                system_instruction=(
                    "You are compiling a math knowledge node. "
                    "Return JSON only with keys summary and detail. "
                    "summary must be concise (1-2 sentences). "
                    "detail must be substantive and reusable as knowledge content."
                ),
                user_message=(
                    f"Title: {title}\n"
                    f"Draft type: {draft_type}\n"
                    f"Draft reason: {reason}\n"
                    f"Question: {job.question}\n"
                    f"Selected text: {job.selection_source_text}\n"
                    "Anchor nodes:\n"
                    + (
                        "\n".join(
                            f"- {node.title}: {node.summary}"
                            for node in anchor_nodes
                        )
                        if anchor_nodes
                        else "- none"
                    )
                    + "\n"
                    + self._symbol_context_prompt(
                        job.symbol_constraints,
                        job.symbol_conflicts,
                    )
                ),
                session_id=job.session_id,
                purpose="knowledge_compile",
            ),
        )
        return self._parse_provider_compiled_content(provider_output.output_text)

    @staticmethod
    def _parse_provider_compiled_content(raw: str) -> tuple[str, str]:
        raw = InMemoryKnowledgeJobRepository._strip_markdown_json_fence(raw)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(
                "Provider compile output must be a valid JSON object with non-empty summary and detail"
            )
        if not isinstance(payload, dict):
            raise ValueError(
                "Provider compile output must be a valid JSON object with non-empty summary and detail"
            )
        summary = payload.get("summary")
        detail = payload.get("detail")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError(
                "Provider compile output must be a valid JSON object with non-empty summary and detail"
            )
        if not isinstance(detail, str) or not detail.strip():
            raise ValueError(
                "Provider compile output must be a valid JSON object with non-empty summary and detail"
            )
        return summary.strip(), detail.strip()

    @staticmethod
    def _strip_markdown_json_fence(value: str) -> str:
        stripped = value.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
        return stripped

    @staticmethod
    def _build_summary(
        title: str,
        question: str,
        anchor_nodes: list[KnowledgeNode],
    ) -> str:
        if anchor_nodes:
            anchor_titles = ", ".join(node.title for node in anchor_nodes)
            return f"{title} connects the question with existing knowledge about {anchor_titles}."
        return f"{title} is an introductory note for {question}."

    @staticmethod
    def _build_detail(
        title: str,
        question: str,
        anchor_nodes: list[KnowledgeNode],
    ) -> str:
        if anchor_nodes:
            anchor_text = " ".join(
                f"{node.title}: {node.summary}" for node in anchor_nodes
            )
            return (
                f"{title}\n\n"
                f"Question: {question}\n\n"
                f"Related knowledge: {anchor_text}"
            )
        else:
            return (
                f"{title}\n\n"
                f"{question}\n\n"
                "This note is a starting point. It should be expanded with a precise "
                "definition, examples, and links to related concepts before it is used "
                "as a stable reference."
            )

    @staticmethod
    def _symbol_context_prompt(
        symbol_constraints: dict[str, str],
        symbol_conflicts: list[str],
    ) -> str:
        lines: list[str] = ["Symbol constraints:"]
        if symbol_constraints:
            lines.extend(
                f"- {symbol}: {meaning}"
                for symbol, meaning in sorted(symbol_constraints.items())
            )
        else:
            lines.append("- none")
        lines.append("Symbol conflicts:")
        if symbol_conflicts:
            lines.extend(f"- {conflict}" for conflict in symbol_conflicts)
        else:
            lines.append("- none")
        return "\n".join(lines)

    @staticmethod
    def _merge_symbols(
        anchor_nodes: list[KnowledgeNode],
        symbol_constraints: dict[str, str] | None = None,
    ) -> dict[str, str]:
        merged: dict[str, str] = {}
        for node in anchor_nodes:
            for symbol, meaning in node.symbols.items():
                merged.setdefault(symbol, meaning)
        merged.update(symbol_constraints or {})
        return merged

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-_")
        return slug or "compiled-knowledge"
