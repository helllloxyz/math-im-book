from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from contextvars import ContextVar
from pathlib import Path
from typing import Final
from uuid import uuid4

from math_im_book.domain.models import (
    AgentStateItem,
    AnswerAnchor,
    ChatSession,
    KnowledgeDraftCandidate,
    ModelSelection,
    OrchestrationPlan,
    ProviderProfile,
    SessionAssistantContext,
    SessionBranchContext,
    SessionForkAnchor,
)


@dataclass(slots=True)
class ProviderResponseMetadata:
    provider_name: str
    raw_response_meta: dict[str, str] = field(default_factory=dict)


_current_provider_response: ContextVar[ProviderResponseMetadata | None] = ContextVar(
    "current_provider_response",
    default=None,
)

_UNCHANGED: Final = object()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_message_id() -> str:
    return f"msg_{uuid4().hex[:12]}"


def remember_provider_response(
    provider_name: str,
    raw_response_meta: dict[str, str] | None = None,
) -> None:
    _current_provider_response.set(
        ProviderResponseMetadata(
            provider_name=provider_name,
            raw_response_meta=raw_response_meta or {},
        )
    )


def clear_provider_response() -> None:
    _current_provider_response.set(None)


@dataclass(slots=True)
class SessionMessage:
    role: str
    content: str
    message_id: str = field(default_factory=_new_message_id)
    created_at: str = field(default_factory=_utcnow)
    provider_name: str | None = None
    raw_response_meta: dict[str, str] = field(default_factory=dict)
    assistant_context: SessionAssistantContext = field(
        default_factory=SessionAssistantContext
    )

    def __post_init__(self) -> None:
        if self.role != "assistant":
            return
        metadata = _current_provider_response.get()
        if metadata is None:
            return
        if self.provider_name is None:
            self.provider_name = metadata.provider_name
        if not self.raw_response_meta:
            self.raw_response_meta = dict(metadata.raw_response_meta)


@dataclass(slots=True)
class SessionWorkingTurn:
    state: str
    user_message: SessionMessage | None = None
    assistant_message: SessionMessage | None = None

    def visible_messages(self) -> list[SessionMessage]:
        messages: list[SessionMessage] = []
        if self.user_message is not None:
            messages.append(self.user_message)
        if self.assistant_message is not None:
            messages.append(self.assistant_message)
        return messages


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    title: str | None = None
    icon: str | None = None
    conversation_model: ModelSelection | None = None
    provider_profile: ProviderProfile | None = None
    default_answer_style_id: str | None = None
    strategy_agent_id: str = "top-down"
    branch_context: SessionBranchContext = field(
        default_factory=lambda: SessionBranchContext()
    )
    messages: list[SessionMessage] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0
    last_committed_message_id: str | None = None
    last_message: SessionMessage | None = None


class FileSessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def index_path(self) -> Path:
        return self.root.parent / "sessions_index.json"

    def get(self, session_id: str) -> ChatSession | None:
        record = self.load_record(session_id)
        if record is None:
            return None
        return ChatSession(
            session_id=record.session_id,
            title=record.title,
            icon=record.icon,
            conversation_model=record.conversation_model,
            provider_profile=record.provider_profile,
            default_answer_style_id=record.default_answer_style_id,
            strategy_agent_id=record.strategy_agent_id,
            branch_context=record.branch_context,
        )

    def list_recent_records(self) -> list[SessionRecord]:
        payload = self._load_index()
        sessions = sorted(
            payload.get("sessions", []),
            key=lambda item: (item.get("updated_at") or "", item["session_id"]),
            reverse=True,
        )
        records: list[SessionRecord] = []
        for item in sessions:
            record = self.load_record(item["session_id"])
            if record is not None:
                records.append(record)
        return records

    def save(self, session: ChatSession) -> None:
        self.save_record(
            SessionRecord(
                session_id=session.session_id,
                title=session.title,
                icon=session.icon,
                conversation_model=session.conversation_model,
                provider_profile=session.provider_profile,
                default_answer_style_id=session.default_answer_style_id,
                strategy_agent_id=session.strategy_agent_id,
                branch_context=session.branch_context,
            )
        )

    def save_record(self, record: SessionRecord) -> None:
        now = _utcnow()
        existing = self._load_session_payload(record.session_id)
        created_at = record.created_at or (
            existing["created_at"] if existing is not None else now
        )
        session_dir = self._session_dir(record.session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        self._write_session_metadata(
            SessionRecord(
                session_id=record.session_id,
                title=record.title,
                icon=record.icon,
                conversation_model=record.conversation_model,
                provider_profile=record.provider_profile,
                default_answer_style_id=record.default_answer_style_id,
                strategy_agent_id=record.strategy_agent_id,
                branch_context=record.branch_context,
                messages=[],
                created_at=created_at,
                updated_at=record.updated_at or now,
                message_count=len(record.messages),
                last_committed_message_id=(
                    record.messages[-1].message_id if record.messages else None
                ),
                last_message=record.messages[-1] if record.messages else None,
            )
        )
        self._write_committed_messages(record.session_id, record.messages)
        self.save_working_turn(record.session_id, None)
        self._update_index_for_session(record.session_id)

    def load_record(self, session_id: str) -> SessionRecord | None:
        metadata = self._load_session_metadata(session_id)
        if metadata is None:
            return None
        return SessionRecord(
            session_id=metadata.session_id,
            title=metadata.title,
            icon=metadata.icon,
            conversation_model=metadata.conversation_model,
            provider_profile=metadata.provider_profile,
            default_answer_style_id=metadata.default_answer_style_id,
            strategy_agent_id=metadata.strategy_agent_id,
            branch_context=metadata.branch_context,
            messages=self.load_visible_messages(session_id),
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            message_count=metadata.message_count,
            last_committed_message_id=metadata.last_committed_message_id,
            last_message=self._last_local_message(session_id),
        )

    def load_local_record(self, session_id: str) -> SessionRecord | None:
        metadata = self._load_session_metadata(session_id)
        if metadata is None:
            return None
        messages = self.load_local_messages(session_id)
        return SessionRecord(
            session_id=metadata.session_id,
            title=metadata.title,
            icon=metadata.icon,
            conversation_model=metadata.conversation_model,
            provider_profile=metadata.provider_profile,
            default_answer_style_id=metadata.default_answer_style_id,
            strategy_agent_id=metadata.strategy_agent_id,
            branch_context=metadata.branch_context,
            messages=messages,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            message_count=metadata.message_count,
            last_committed_message_id=metadata.last_committed_message_id,
            last_message=messages[-1] if messages else None,
        )

    def update_record(
        self,
        session_id: str,
        *,
        title: str | None | object = _UNCHANGED,
        icon: str | None | object = _UNCHANGED,
        conversation_model: ModelSelection | None | object = _UNCHANGED,
        provider_profile: ProviderProfile | None | object = _UNCHANGED,
        branch_context: SessionBranchContext | object = _UNCHANGED,
        strategy_agent_id: str | object = _UNCHANGED,
    ) -> SessionRecord:
        record = self.load_local_record(session_id)
        if record is None:
            raise FileNotFoundError(session_id)
        updated = SessionRecord(
            session_id=record.session_id,
            title=record.title if title is _UNCHANGED else title,
            icon=record.icon if icon is _UNCHANGED else icon,
            conversation_model=(
                record.conversation_model
                if conversation_model is _UNCHANGED
                else conversation_model
            ),
            provider_profile=(
                record.provider_profile
                if provider_profile is _UNCHANGED
                else provider_profile
            ),
            default_answer_style_id=record.default_answer_style_id,
            strategy_agent_id=(
                record.strategy_agent_id
                if strategy_agent_id is _UNCHANGED
                else strategy_agent_id
            ),
            branch_context=(
                record.branch_context
                if branch_context is _UNCHANGED
                else branch_context
            ),
            messages=record.messages,
            created_at=record.created_at,
        )
        self.save_record(updated)
        return self.load_record(session_id)  # type: ignore[return-value]

    def append_messages(
        self,
        session_id: str,
        messages: list[SessionMessage],
        *,
        branch_context: SessionBranchContext | object = _UNCHANGED,
        title: str | None | object = _UNCHANGED,
        icon: str | None | object = _UNCHANGED,
        conversation_model: ModelSelection | None | object = _UNCHANGED,
        provider_profile: ProviderProfile | None | object = _UNCHANGED,
        strategy_agent_id: str | object = _UNCHANGED,
    ) -> SessionRecord:
        record = self.load_local_record(session_id)
        if record is None:
            raise FileNotFoundError(session_id)
        local_messages = [*record.messages, *messages]
        updated = SessionRecord(
            session_id=record.session_id,
            title=record.title if title is _UNCHANGED else title,
            icon=record.icon if icon is _UNCHANGED else icon,
            conversation_model=(
                record.conversation_model
                if conversation_model is _UNCHANGED
                else conversation_model
            ),
            provider_profile=(
                record.provider_profile
                if provider_profile is _UNCHANGED
                else provider_profile
            ),
            default_answer_style_id=record.default_answer_style_id,
            strategy_agent_id=(
                record.strategy_agent_id
                if strategy_agent_id is _UNCHANGED
                else strategy_agent_id
            ),
            branch_context=(
                record.branch_context
                if branch_context is _UNCHANGED
                else branch_context
            ),
            messages=local_messages,
            created_at=record.created_at,
        )
        self.save_record(updated)
        return self.load_record(session_id)  # type: ignore[return-value]

    def load_local_messages(self, session_id: str) -> list[SessionMessage]:
        path = self._messages_path(session_id)
        if not path.exists():
            return []
        messages: list[SessionMessage] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            messages.append(_deserialize_message(json.loads(line)))
        return messages

    def load_visible_messages(self, session_id: str) -> list[SessionMessage]:
        committed = self._load_visible_committed_messages(session_id)
        working_turn = self.load_working_turn(session_id)
        if working_turn is None:
            return committed
        return [*committed, *working_turn.visible_messages()]

    def load_working_turn(self, session_id: str) -> SessionWorkingTurn | None:
        path = self._working_turn_path(session_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload is None:
            return None
        return SessionWorkingTurn(
            state=payload["state"],
            user_message=(
                _deserialize_message(payload["user_message"])
                if payload.get("user_message") is not None
                else None
            ),
            assistant_message=(
                _deserialize_message(payload["assistant_message"])
                if payload.get("assistant_message") is not None
                else None
            ),
        )

    def save_working_turn(
        self,
        session_id: str,
        working_turn: SessionWorkingTurn | None,
    ) -> None:
        path = self._working_turn_path(session_id)
        if working_turn is None:
            if path.exists():
                path.unlink()
            return
        path.write_text(
            json.dumps(
                {
                    "state": working_turn.state,
                    "user_message": (
                        _serialize_message(working_turn.user_message)
                        if working_turn.user_message is not None
                        else None
                    ),
                    "assistant_message": (
                        _serialize_message(working_turn.assistant_message)
                        if working_turn.assistant_message is not None
                        else None
                    ),
                }
            ),
            encoding="utf-8",
        )
        self._touch_updated_at(session_id)

    def has_working_message_id(self, session_id: str, message_id: str) -> bool:
        working_turn = self.load_working_turn(session_id)
        if working_turn is None:
            return False
        return any(message.message_id == message_id for message in working_turn.visible_messages())

    def find_committed_message(
        self, session_id: str, message_id: str
    ) -> SessionMessage | None:
        for message in self._load_visible_committed_messages(session_id):
            if message.message_id == message_id:
                return message
        return None

    def delete_record(self, session_id: str) -> None:
        path = self._session_dir(session_id)
        if path.exists():
            shutil.rmtree(path)
        self._remove_from_index(session_id)

    def _load_visible_committed_messages(self, session_id: str) -> list[SessionMessage]:
        metadata = self._load_session_metadata(session_id)
        if metadata is None:
            return []
        inherited: list[SessionMessage] = []
        parent_session_id = metadata.branch_context.parent_session_id
        if parent_session_id is not None:
            inherited = self._load_visible_committed_messages(parent_session_id)
            inherited = self._truncate_messages(
                inherited,
                metadata.branch_context.fork_anchor,
            )
        return [*inherited, *self.load_local_messages(session_id)]

    def _truncate_messages(
        self,
        messages: list[SessionMessage],
        fork_anchor: SessionForkAnchor | None,
    ) -> list[SessionMessage]:
        if fork_anchor is None:
            return messages
        cutoff_id = fork_anchor.message_id or fork_anchor.source_message_id
        if cutoff_id is None:
            return messages
        truncated: list[SessionMessage] = []
        for message in messages:
            truncated.append(message)
            if message.message_id == cutoff_id:
                return truncated
        return messages

    def _last_local_message(self, session_id: str) -> SessionMessage | None:
        messages = self.load_local_messages(session_id)
        if messages:
            return messages[-1]
        working_turn = self.load_working_turn(session_id)
        if working_turn is None:
            return None
        visible = working_turn.visible_messages()
        return visible[-1] if visible else None

    def _touch_updated_at(self, session_id: str) -> None:
        record = self.load_local_record(session_id)
        if record is None:
            return
        self._write_session_metadata(
            SessionRecord(
                session_id=record.session_id,
                title=record.title,
                icon=record.icon,
                provider_profile=record.provider_profile,
                default_answer_style_id=record.default_answer_style_id,
                strategy_agent_id=record.strategy_agent_id,
                branch_context=record.branch_context,
                messages=[],
                created_at=record.created_at,
                updated_at=_utcnow(),
                message_count=record.message_count,
                last_committed_message_id=record.last_committed_message_id,
                last_message=record.last_message,
            )
        )
        self._update_index_for_session(session_id)

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _session_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "session.json"

    def _messages_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "messages.jsonl"

    def _working_turn_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "working_turn.json"

    def _write_committed_messages(
        self, session_id: str, messages: list[SessionMessage]
    ) -> None:
        path = self._messages_path(session_id)
        lines = [json.dumps(_serialize_message(message)) for message in messages]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _load_session_payload(self, session_id: str) -> dict[str, object] | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_session_metadata(self, session_id: str) -> SessionRecord | None:
        payload = self._load_session_payload(session_id)
        if payload is None:
            return None
        conversation_payload = payload.get("conversation_model")
        conversation_model = _deserialize_model_selection(conversation_payload)
        profile_payload = payload.get("provider_profile")
        provider_profile = _deserialize_provider_profile(profile_payload)
        branch_payload = payload.get("branch")
        return SessionRecord(
            session_id=payload["session_id"],
            title=payload.get("title"),
            icon=payload.get("icon"),
            conversation_model=conversation_model,
            provider_profile=provider_profile,
            default_answer_style_id=(
                str(payload["default_answer_style_id"])
                if payload.get("default_answer_style_id") is not None
                else None
            ),
            strategy_agent_id=str(payload.get("strategy_agent_id") or "top-down"),
            branch_context=_deserialize_branch(branch_payload),
            messages=[],
            created_at=payload.get("created_at"),
            updated_at=payload.get("updated_at"),
            message_count=payload.get("message_count", 0),
            last_committed_message_id=payload.get("last_committed_message_id"),
        )

    def _write_session_metadata(self, record: SessionRecord) -> None:
        path = self._session_path(record.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "version": 3,
                    "session_id": record.session_id,
                    "title": record.title,
                    "icon": record.icon,
                    "default_answer_style_id": record.default_answer_style_id,
                    "strategy_agent_id": record.strategy_agent_id,
                    "created_at": record.created_at or _utcnow(),
                    "updated_at": record.updated_at or _utcnow(),
                    "message_count": record.message_count,
                    "last_committed_message_id": record.last_committed_message_id,
                    "conversation_model": _serialize_model_selection(
                        record.conversation_model
                    ),
                    "provider_profile": _serialize_provider_profile(
                        record.provider_profile
                    ),
                    "branch": _serialize_branch(record.branch_context),
                }
            ),
            encoding="utf-8",
        )

    def _load_index(self) -> dict[str, list[dict[str, object]]]:
        if not self.index_path.exists():
            return {"sessions": []}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, payload: dict[str, list[dict[str, object]]]) -> None:
        self.index_path.write_text(json.dumps(payload), encoding="utf-8")

    def _update_index_for_session(self, session_id: str) -> None:
        metadata = self._load_session_metadata(session_id)
        if metadata is None:
            return
        last_message = self._last_local_message(session_id)
        payload = self._load_index()
        sessions = [
            item for item in payload.get("sessions", []) if item["session_id"] != session_id
        ]
        sessions.append(
            {
                "session_id": session_id,
                "title": metadata.title,
                "icon": metadata.icon,
                "updated_at": metadata.updated_at,
                "message_count": metadata.message_count,
                "last_preview": (
                    last_message.content[:120] if last_message is not None else None
                ),
                "parent_session_id": metadata.branch_context.parent_session_id,
                "root_session_id": metadata.branch_context.root_session_id
                or metadata.session_id,
            }
        )
        self._save_index({"sessions": sessions})

    def _remove_from_index(self, session_id: str) -> None:
        payload = self._load_index()
        self._save_index(
            {
                "sessions": [
                    item
                    for item in payload.get("sessions", [])
                    if item["session_id"] != session_id
                ]
            }
        )


def _serialize_provider_profile(
    profile: ProviderProfile | None,
) -> dict[str, object] | None:
    if profile is None:
        return None
    return {
        "provider_type": profile.provider_type,
        "model": profile.model,
        "credential_id": profile.credential_id,
        "base_url": profile.base_url,
        "options": profile.options,
    }


def _deserialize_provider_profile(
    payload: object,
) -> ProviderProfile | None:
    if not isinstance(payload, dict):
        return None
    return ProviderProfile(
        provider_type=payload["provider_type"],
        model=payload["model"],
        credential_id=payload["credential_id"],
        base_url=payload.get("base_url"),
        options=dict(payload.get("options", {})),
    )


def _serialize_model_selection(
    selection: ModelSelection | None,
) -> dict[str, object] | None:
    if selection is None:
        return None
    return {
        "provider_id": selection.provider_id,
        "provider_type": selection.provider_type,
        "model": selection.model,
        "credential_id": selection.credential_id,
    }


def _deserialize_model_selection(payload: object) -> ModelSelection | None:
    if not isinstance(payload, dict):
        return None
    provider_type = payload.get("provider_type")
    model = payload.get("model")
    if not provider_type or not model:
        return None
    return ModelSelection(
        provider_id=payload.get("provider_id"),
        provider_type=str(provider_type),
        model=str(model),
        credential_id=(
            str(payload["credential_id"]) if payload.get("credential_id") else None
        ),
    )


def _serialize_branch(branch: SessionBranchContext) -> dict[str, object]:
    return {
        "branch_id": branch.branch_id,
        "parent_session_id": branch.parent_session_id,
        "root_session_id": branch.root_session_id,
        "focus_question": branch.focus_question,
        "fork_anchor": _serialize_fork_anchor(branch.fork_anchor),
        "active_node_ids": list(branch.active_node_ids),
        "summary_node_ids": list(branch.summary_node_ids),
        "active_symbols": dict(branch.active_symbols),
        "knowledge_scope_id": branch.knowledge_scope_id,
    }


def _deserialize_branch(payload: object) -> SessionBranchContext:
    if not isinstance(payload, dict):
        return SessionBranchContext()
    return SessionBranchContext(
        branch_id=payload.get("branch_id"),
        parent_session_id=payload.get("parent_session_id"),
        root_session_id=payload.get("root_session_id"),
        focus_question=payload.get("focus_question"),
        fork_anchor=_deserialize_fork_anchor(payload.get("fork_anchor")),
        active_node_ids=list(payload.get("active_node_ids") or []),
        summary_node_ids=list(payload.get("summary_node_ids") or []),
        active_symbols=dict(payload.get("active_symbols") or {}),
        knowledge_scope_id=(
            str(payload["knowledge_scope_id"])
            if payload.get("knowledge_scope_id")
            else None
        ),
    )


def _serialize_fork_anchor(anchor: SessionForkAnchor | None) -> dict[str, object] | None:
    if anchor is None:
        return None
    return {
        "type": anchor.type,
        "message_id": anchor.message_id,
        "node_id": anchor.node_id,
        "source_message_id": anchor.source_message_id,
    }


def _deserialize_fork_anchor(payload: object) -> SessionForkAnchor | None:
    if not isinstance(payload, dict):
        return None
    return SessionForkAnchor(
        type=payload["type"],
        message_id=payload.get("message_id"),
        node_id=payload.get("node_id"),
        source_message_id=payload.get("source_message_id"),
    )


def _serialize_message(message: SessionMessage) -> dict[str, object]:
    return {
        "message_id": message.message_id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
        "provider_name": message.provider_name,
        "raw_response_meta": message.raw_response_meta,
        "assistant_context": {
            "action_type": message.assistant_context.action_type,
            "referenced_node_ids": message.assistant_context.referenced_node_ids,
            "anchors": [
                {
                    "anchor_id": anchor.anchor_id,
                    "label": anchor.label,
                    "status": anchor.status,
                    "node_id": anchor.node_id,
                }
                for anchor in message.assistant_context.anchors
            ],
            "symbol_conflicts": message.assistant_context.symbol_conflicts,
            "alignment_notes": message.assistant_context.alignment_notes,
            "compact_summary": message.assistant_context.compact_summary,
            "orchestration_plan": _serialize_orchestration_plan(
                message.assistant_context.orchestration_plan
            ),
            "state_items": [
                _serialize_agent_state_item(item)
                for item in message.assistant_context.state_items
            ],
        },
    }


def _deserialize_message(payload: dict[str, object]) -> SessionMessage:
    return SessionMessage(
        message_id=payload.get("message_id") or _new_message_id(),
        role=payload["role"],
        content=payload["content"],
        created_at=payload.get("created_at") or _utcnow(),
        provider_name=payload.get("provider_name"),
        raw_response_meta=dict(payload.get("raw_response_meta") or {}),
        assistant_context=_load_assistant_context(payload),
    )


def _load_assistant_context(item: dict[str, object]) -> SessionAssistantContext:
    raw_context = item.get("assistant_context")
    if isinstance(raw_context, dict):
        return SessionAssistantContext(
            action_type=raw_context.get("action_type"),
            referenced_node_ids=list(raw_context.get("referenced_node_ids") or []),
            anchors=_load_anchors(raw_context.get("anchors")),
            symbol_conflicts=list(raw_context.get("symbol_conflicts") or []),
            alignment_notes=list(raw_context.get("alignment_notes") or []),
            compact_summary=raw_context.get("compact_summary"),
            orchestration_plan=_deserialize_orchestration_plan(
                raw_context.get("orchestration_plan")
            ),
            state_items=_deserialize_agent_state_items(
                raw_context.get("state_items")
            ),
        )
    if (
        "action_type" in item
        or "referenced_node_ids" in item
        or "anchors" in item
        or "symbol_conflicts" in item
        or "alignment_notes" in item
        or "compact_summary" in item
        or "orchestration_plan" in item
        or "state_items" in item
    ):
        return SessionAssistantContext(
            action_type=item.get("action_type"),
            referenced_node_ids=list(item.get("referenced_node_ids") or []),
            anchors=_load_anchors(item.get("anchors")),
            symbol_conflicts=list(item.get("symbol_conflicts") or []),
            alignment_notes=list(item.get("alignment_notes") or []),
            compact_summary=item.get("compact_summary"),
            orchestration_plan=_deserialize_orchestration_plan(
                item.get("orchestration_plan")
            ),
            state_items=_deserialize_agent_state_items(item.get("state_items")),
        )
    return SessionAssistantContext()


def _serialize_orchestration_plan(
    plan: OrchestrationPlan | None,
) -> dict[str, object] | None:
    if plan is None:
        return None
    return {
        "route": plan.route,
        "intent": plan.intent,
        "persistence_decision": plan.persistence_decision,
        "confidence": plan.confidence,
        "user_visible_summary": plan.user_visible_summary,
        "detected_scope_ids": list(plan.detected_scope_ids),
        "profile_layers_used": list(plan.profile_layers_used),
        "profile_context_summary": plan.profile_context_summary,
        "candidate_drafts": [
            {
                "title": draft.title,
                "draft_type": draft.draft_type,
                "reason": draft.reason,
            }
            for draft in plan.candidate_drafts
        ],
        "strategy_mode": plan.strategy_mode,
        "strategy_reason": plan.strategy_reason,
        "knowledge_scope_id": plan.knowledge_scope_id,
        "knowledge_scope_label": plan.knowledge_scope_label,
    }


def _deserialize_orchestration_plan(payload: object) -> OrchestrationPlan | None:
    if not isinstance(payload, dict):
        return None
    route = payload.get("route")
    intent = payload.get("intent")
    persistence_decision = payload.get("persistence_decision")
    user_visible_summary = payload.get("user_visible_summary")
    if not all(
        isinstance(value, str) and value
        for value in (route, intent, persistence_decision, user_visible_summary)
    ):
        return None
    return OrchestrationPlan(
        route=route,
        intent=intent,
        persistence_decision=persistence_decision,
        confidence=float(payload.get("confidence") or 0.0),
        user_visible_summary=user_visible_summary,
        detected_scope_ids=[
            item
            for item in payload.get("detected_scope_ids") or []
            if isinstance(item, str)
        ],
        profile_layers_used=[
            item
            for item in payload.get("profile_layers_used") or []
            if isinstance(item, str)
        ],
        profile_context_summary=(
            payload["profile_context_summary"]
            if isinstance(payload.get("profile_context_summary"), str)
            else None
        ),
        candidate_drafts=_deserialize_knowledge_draft_candidates(
            payload.get("candidate_drafts")
        ),
        strategy_mode=(
            payload["strategy_mode"]
            if payload.get("strategy_mode") in {"top-down", "raw"}
            else "top-down"
        ),
        strategy_reason=(
            payload["strategy_reason"]
            if isinstance(payload.get("strategy_reason"), str)
            else ""
        ),
        knowledge_scope_id=(
            payload["knowledge_scope_id"]
            if isinstance(payload.get("knowledge_scope_id"), str)
            else None
        ),
        knowledge_scope_label=(
            payload["knowledge_scope_label"]
            if isinstance(payload.get("knowledge_scope_label"), str)
            else "全部知识"
        ),
    )


def _deserialize_knowledge_draft_candidates(
    payload: object,
) -> list[KnowledgeDraftCandidate]:
    if not isinstance(payload, list):
        return []
    candidates: list[KnowledgeDraftCandidate] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        draft_type = item.get("draft_type")
        reason = item.get("reason")
        if not all(
            isinstance(value, str) and value
            for value in (title, draft_type, reason)
        ):
            continue
        candidates.append(
            KnowledgeDraftCandidate(
                title=title,
                draft_type=draft_type,
                reason=reason,
            )
        )
    return candidates


def _serialize_agent_state_item(item: AgentStateItem) -> dict[str, object]:
    return {
        "item_id": item.item_id,
        "kind": item.kind,
        "state": item.state,
        "title": item.title,
        "reason": item.reason,
        "source_message_id": item.source_message_id,
        "node_id": item.node_id,
        "error_message": item.error_message,
    }


def _deserialize_agent_state_items(payload: object) -> list[AgentStateItem]:
    if not isinstance(payload, list):
        return []
    items: list[AgentStateItem] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        item_id = item.get("item_id")
        kind = item.get("kind")
        state = item.get("state")
        title = item.get("title")
        reason = item.get("reason")
        if not all(
            isinstance(value, str) and value
            for value in (item_id, kind, state, title, reason)
        ):
            continue
        source_message_id = item.get("source_message_id")
        node_id = item.get("node_id")
        error_message = item.get("error_message")
        items.append(
            AgentStateItem(
                item_id=item_id,
                kind=kind,
                state=state,
                title=title,
                reason=reason,
                source_message_id=(
                    source_message_id if isinstance(source_message_id, str) else None
                ),
                node_id=node_id if isinstance(node_id, str) else None,
                error_message=error_message if isinstance(error_message, str) else None,
            )
        )
    return items


def _load_anchors(payload: object) -> list[AnswerAnchor]:
    if not isinstance(payload, list):
        return []
    anchors: list[AnswerAnchor] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        anchor_id = item.get("anchor_id")
        label = item.get("label")
        status = item.get("status")
        if not all(isinstance(value, str) and value for value in (anchor_id, label, status)):
            continue
        node_id = item.get("node_id")
        anchors.append(
            AnswerAnchor(
                anchor_id=anchor_id,
                label=label,
                status=status,
                node_id=node_id if isinstance(node_id, str) and node_id else None,
            )
        )
    return anchors
