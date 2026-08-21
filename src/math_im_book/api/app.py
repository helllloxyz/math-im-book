import json
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from threading import Thread
from time import perf_counter
from typing import Callable, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from math_im_book.api.schemas import (
    AgentDecisionSummarySchema,
    AgentStateResponseSchema,
    AgentTurnStateSchema,
    AgentStateItemSchema,
    AskRequestSchema,
    AskResponseSchema,
    AnswerAnchorSchema,
    AnswerStyleSchema,
    AnswerStylesResponseSchema,
    CompactRequestSchema,
    ContextHealthSchema,
    DefaultModelSelectionSchema,
    DefaultOptionsSchema,
    ExplorerFolderCreateSchema,
    ExplorerFolderResponseSchema,
    ExplorerFolderUpdateSchema,
    ExplorerItemIconResponseSchema,
    ExplorerItemIconUpdateSchema,
    ExplorerItemLocationResponseSchema,
    ExplorerItemLocationUpdateSchema,
    ExplorerOrganizeResponseSchema,
    ExplorerTreeResponseSchema,
    KnowledgeDraftCandidateSchema,
    KnowledgeAuthorizationDecisionSchema,
    KnowledgeJobSchema,
    KnowledgeNodeUpdateSchema,
    KnowledgeQueueItemSchema,
    MemoryScopeStateSchema,
    NodeResponseSchema,
    OutlineResponseSchema,
    ProviderOptionsResponseSchema,
    ProviderProfileSchema,
    OrchestrationPlanSchema,
    RegenerateRequestSchema,
    SelectionKnowledgeDraftRequestSchema,
    SessionBranchSchema,
    SessionForkRequestSchema,
    SessionForkAnchorSchema,
    SessionAssistantContextSchema,
    SessionListItemSchema,
    SessionMessageSchema,
    SessionSchema,
    SessionsListResponseSchema,
    StrategyAgentSchema,
    StrategyAgentsResponseSchema,
)
from math_im_book.domain.models import (
    AgentStateItem,
    AnswerAnchor,
    KnowledgeNode,
    KnowledgeDraftCandidate,
    ModelSelection,
    OrchestrationPlan,
    PendingDraftRequest,
    NodeReference,
    ProviderProfile,
    SessionAssistantContext,
    SessionBranchContext,
    SessionForkAnchor,
)
from math_im_book.services.context_selector import ContextSelector
from math_im_book.services.knowledge_jobs import InMemoryKnowledgeJobRepository
from math_im_book.services.orchestrator import KnowledgeOrchestrator
from math_im_book.services.planner import (
    PlannerError,
    QuestionPlanner,
)
from math_im_book.services.providers import (
    ProviderError,
    ProviderAuthenticationError,
    ProviderGateway,
    ProviderRequest,
    ProviderRateLimitError,
    ProviderUpstreamError,
    UnsupportedProviderError,
)
from math_im_book.services.runtime_logging import get_runtime_logger, safe_log_value
from math_im_book.services.symbols import SymbolRegistry
from math_im_book.storage.answer_styles import FileAnswerStyleRepository
from math_im_book.storage.credentials import FileCredentialRegistry
from math_im_book.storage.explorer import (
    ExplorerError,
    ExplorerFolder,
    ExplorerFolderConflictError,
    ExplorerInvalidMoveError,
    ExplorerStore,
)
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.provider_options import FileProviderOptionsRegistry
from math_im_book.storage.strategy_agents import FileStrategyAgentRepository
from math_im_book.storage.sessions import (
    FileSessionStore,
    SessionMessage,
    SessionRecord,
    SessionWorkingTurn,
)
from math_im_book.storage.user_profile import FileUserProfileRepository

MATH_SESSION_CATEGORIES = {
    "algebra": "Algebraic expressions, equations, polynomials, and symbolic manipulation",
    "geometry": "Euclidean, analytic, projective, and differential geometry",
    "linear-algebra": "Vectors, matrices, linear maps, eigenvalues, and tensors",
    "calculus-analysis": "Calculus, real or complex analysis, limits, series, and measure theory",
    "group-theory": "Groups, rings, fields, representations, symmetry, and abstract algebra",
    "number-theory": "Integers, primes, Diophantine equations, and arithmetic",
    "probability-statistics": "Probability, statistics, stochastic processes, and inference",
    "discrete-combinatorics": "Combinatorics, graph theory, algorithms, and discrete structures",
    "logic-foundations": "Logic, set theory, category theory, type theory, and foundations",
    "topology": "Topology, manifolds, knots, homotopy, and related spaces",
    "applied-modeling": "Differential equations, numerical methods, optimization, physics, and modeling",
    "general": "Mixed, elementary, historical, or otherwise cross-category mathematics",
}
DEFAULT_SESSION_CATEGORY = "general"
DEFAULT_STRATEGY_AGENT_ID = "top-down"

logger = get_runtime_logger("api")


def _log_question_failure(
    session_id: str | None,
    started_at: float,
    reason: str,
    exc: Exception,
) -> None:
    logger.warning(
        "Question generation failed: session=%s reason=%s duration_ms=%d "
        "error=%s detail=%s",
        safe_log_value(session_id),
        reason,
        round((perf_counter() - started_at) * 1000),
        type(exc).__name__,
        safe_log_value(exc),
    )


class CredentialWriteSchema(BaseModel):
    credential_id: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    provider_type: str | None = None
    provider_id: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    base_url: str | None = None
    default_model: str | None = None
    models: list[str] = Field(default_factory=list)


class CredentialUpdateSchema(BaseModel):
    credential_id: str | None = None
    api_key: str | None = Field(default=None, min_length=1)
    provider_type: str | None = None
    provider_id: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    base_url: str | None = None
    default_model: str | None = None
    models: list[str] = Field(default_factory=list)


class SessionUpdateSchema(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    icon: str | None = Field(default=None, min_length=1)
    conversation_model: DefaultModelSelectionSchema | None = None
    knowledge_approval_policy: Literal[
        "agent_decides", "always_ask", "full_auto"
    ] | None = None


class CompileSuggestedDraftsRequestSchema(BaseModel):
    draft_indexes: list[int] = Field(min_length=1)


def create_app(
    repository: MarkdownKnowledgeRepository | None = None,
    credential_registry: FileCredentialRegistry | None = None,
    session_store: FileSessionStore | None = None,
    provider_gateway: ProviderGateway | None = None,
    provider_options_registry: FileProviderOptionsRegistry | None = None,
    knowledge_job_repository: InMemoryKnowledgeJobRepository | None = None,
    explorer_store: ExplorerStore | None = None,
) -> FastAPI:
    app = FastAPI(title="math-im-book")

    # Path to the new Vue frontend dist directory
    frontend_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    frontend_public = Path(__file__).resolve().parents[3] / "frontend" / "public"

    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")
        favicon_path = frontend_dist / "favicon.png"
        if favicon_path.exists():

            @app.get("/favicon.png", include_in_schema=False)
            @app.get("/favicon.ico", include_in_schema=False)
            def favicon() -> FileResponse:
                return FileResponse(favicon_path, media_type="image/png")

        provider_icons_dir = frontend_public / "provider-icons"
        if not provider_icons_dir.exists():
            provider_icons_dir = frontend_dist / "provider-icons"
        if provider_icons_dir.exists():
            app.mount(
                "/provider-icons",
                StaticFiles(directory=provider_icons_dir),
                name="provider-icons",
            )

        @app.get("/", response_class=HTMLResponse)
        def frontend() -> str:
            index_path = frontend_dist / "index.html"
            return index_path.read_text(encoding="utf-8")
    else:
        provider_icons_dir = frontend_public / "provider-icons"
        if provider_icons_dir.exists():
            app.mount(
                "/provider-icons",
                StaticFiles(directory=provider_icons_dir),
                name="provider-icons",
            )

        # Fallback for development if dist doesn't exist yet
        @app.get("/", response_class=HTMLResponse)
        def frontend() -> str:
            return "<h1>Frontend not built</h1><p>Run <code>npm run build</code> in the frontend directory.</p>"

    knowledge_repository = repository or MarkdownKnowledgeRepository(
        Path("data/knowledge")
    )
    credentials = credential_registry or FileCredentialRegistry(
        Path("data/credentials/credentials.json")
    )
    provider_options = provider_options_registry or FileProviderOptionsRegistry(
        Path("data/config/provider_options.json")
    )
    answer_styles = FileAnswerStyleRepository(Path("data/config/answer_styles"))
    strategy_agents = FileStrategyAgentRepository(
        Path("data/config/strategy_agents")
    )
    user_profile = FileUserProfileRepository()
    sessions = session_store or FileSessionStore(Path("data/chats/sessions"))
    explorer = explorer_store or ExplorerStore(Path("data/explorer/index.json"))
    resolved_provider_gateway = provider_gateway or ProviderGateway(credentials)
    resolved_knowledge_job_repository = knowledge_job_repository or InMemoryKnowledgeJobRepository(
        knowledge_repository,
        provider_gateway=resolved_provider_gateway,
        explorer_store=explorer,
    )

    orchestrator = KnowledgeOrchestrator(
        repository=knowledge_repository,
        planner=QuestionPlanner(
            provider_gateway=resolved_provider_gateway,
            user_profile_repository=user_profile,
        ),
        context_selector=ContextSelector(
            knowledge_repository,
            scope_node_ids_resolver=lambda scope_id: explorer.list_item_ids_in_folder(
                item_type="knowledge_node",
                folder_id=scope_id,
                include_descendants=True,
            ),
        ),
        provider_gateway=resolved_provider_gateway,
        knowledge_job_repository=resolved_knowledge_job_repository,
        answer_style_repository=answer_styles,
        strategy_agent_repository=strategy_agents,
        user_profile_repository=user_profile,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/credentials")
    def list_credentials() -> dict[str, list[dict[str, object]]]:
        return {"credentials": _credential_summaries(credentials)}

    @app.get("/api/provider-options", response_model=ProviderOptionsResponseSchema)
    def list_provider_options() -> ProviderOptionsResponseSchema:
        return ProviderOptionsResponseSchema.model_validate(provider_options.load())

    @app.put(
        "/api/provider-options/default-options",
        response_model=DefaultOptionsSchema,
    )
    def update_default_options(
        payload: DefaultOptionsSchema,
    ) -> DefaultOptionsSchema:
        current = provider_options.load()
        current["default_options"] = payload.model_dump()
        provider_options.save(current)
        return payload

    @app.get("/api/answer-styles", response_model=AnswerStylesResponseSchema)
    def list_answer_styles() -> AnswerStylesResponseSchema:
        catalog = answer_styles.load()
        return AnswerStylesResponseSchema.model_validate(
            {
                "default_style_id": catalog.default_style_id,
                "styles": [
                    AnswerStyleSchema(
                        answer_style_id=style.style_id,
                        label=style.label,
                        description=style.description,
                        instructions=style.instructions,
                        is_default=style.is_default,
                    ).model_dump()
                    for style in catalog.styles
                ],
            }
        )

    @app.get("/api/strategy-agents", response_model=StrategyAgentsResponseSchema)
    def list_strategy_agents() -> StrategyAgentsResponseSchema:
        catalog = strategy_agents.load()
        return StrategyAgentsResponseSchema.model_validate(
            {
                "default_strategy_agent_id": catalog.default_strategy_agent_id,
                "agents": [
                    StrategyAgentSchema(
                        strategy_agent_id=agent.strategy_agent_id,
                        label=agent.label,
                        description=agent.description,
                        instructions=agent.instructions,
                        is_default=agent.is_default,
                    ).model_dump()
                    for agent in catalog.agents
                ],
            }
        )

    def configured_default_strategy_agent_id() -> str:
        catalog = strategy_agents.load()
        return catalog.default_strategy_agent_id or DEFAULT_STRATEGY_AGENT_ID

    @app.post("/api/credentials")
    def create_credential(payload: CredentialWriteSchema) -> dict[str, dict[str, object]]:
        return {"credential": _upsert_credential(credentials, payload)}

    @app.put("/api/credentials/{credential_id}")
    def update_credential(
        credential_id: str, payload: CredentialUpdateSchema
    ) -> dict[str, dict[str, object]]:
        if payload.credential_id is not None and payload.credential_id != credential_id:
            raise HTTPException(
                status_code=400, detail="credential_id must match the path parameter"
            )
        return {
            "credential": _upsert_credential(
                credentials,
                CredentialWriteSchema(
                    credential_id=credential_id,
                    api_key=payload.api_key or _credential_api_key(credentials, credential_id),
                    provider_type=payload.provider_type,
                    provider_id=payload.provider_id,
                    headers=payload.headers,
                    base_url=payload.base_url,
                    default_model=payload.default_model,
                    models=payload.models,
                ),
            )
        }

    def _answer_question(
        *,
        question: str,
        session_id: str | None,
        provider_profile: ProviderProfile | None,
        branch_context: SessionBranchContext | None,
        answer_style_id: str | None,
        strategy_agent_id: str | None,
        knowledge_approval_policy: str,
        stream_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ):
        started_at = perf_counter()
        logger.info(
            "Question generation started: session=%s mode=%s provider=%s model=%s",
            safe_log_value(session_id),
            "stream" if stream_callback is not None else "standard",
            safe_log_value(provider_profile.provider_type if provider_profile else "local"),
            safe_log_value(provider_profile.model if provider_profile else None),
        )
        try:
            result = orchestrator.answer(
                question,
                session_id=session_id,
                provider_profile=provider_profile,
                branch_context=_meaningful_branch_context(branch_context),
                answer_style_id=answer_style_id,
                strategy_agent_id=strategy_agent_id,
                knowledge_approval_policy=knowledge_approval_policy,
                stream_callback=stream_callback,
                progress_callback=progress_callback,
            )
        except KeyError as exc:
            _log_question_failure(session_id, started_at, "configuration", exc)
            raise HTTPException(status_code=400, detail="Unknown answer style") from exc
        except ProviderAuthenticationError as exc:
            _log_question_failure(session_id, started_at, "provider_authentication", exc)
            raise HTTPException(
                status_code=502, detail="Provider authentication failed"
            ) from exc
        except ProviderRateLimitError as exc:
            _log_question_failure(session_id, started_at, "provider_rate_limit", exc)
            raise HTTPException(
                status_code=429, detail="Provider rate limit exceeded"
            ) from exc
        except (ProviderUpstreamError, UnsupportedProviderError) as exc:
            _log_question_failure(session_id, started_at, "provider_upstream", exc)
            raise HTTPException(status_code=502, detail="Provider request failed") from exc
        except PlannerError as exc:
            _log_question_failure(session_id, started_at, "planner", exc)
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            _log_question_failure(session_id, started_at, "unexpected", exc)
            raise
        plan = result.orchestration_plan or result.action.orchestration_plan
        logger.info(
            "Question generation completed: session=%s route=%s action=%s "
            "selected_nodes=%d drafts=%d knowledge_job=%s duration_ms=%d",
            safe_log_value(session_id),
            safe_log_value(plan.route if plan is not None else None),
            safe_log_value(result.action.action_type),
            len(result.action.selected_node_ids),
            len(result.drafts),
            safe_log_value(result.answer.knowledge_job_id),
            round((perf_counter() - started_at) * 1000),
        )
        return result

    def _ask_response(
        payload: AskRequestSchema,
        stream_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> AskResponseSchema:
        session_id = payload.session_id or f"chat-{uuid4().hex[:8]}"
        existing_record = (
            sessions.load_record(session_id)
            if payload.session_id
            else None
        )
        provider_options_payload = provider_options.load()
        conversation_model = _resolved_conversation_model_selection(
            payload=payload,
            existing_record=existing_record,
            provider_options_payload=provider_options_payload,
            provider_profile=(
                _schema_to_provider_profile(payload.provider_profile)
                if payload.provider_profile is not None
                else None
            ),
        )
        provider_profile = (
            _schema_to_provider_profile(payload.provider_profile)
            if payload.provider_profile is not None
            else _resolve_provider_profile_from_selection(
                selection=conversation_model,
                credential_registry=credentials,
                provider_options_payload=provider_options_payload,
            )
            or (existing_record.provider_profile if existing_record is not None else None)
        )
        strategy_agent_id = (
            payload.strategy_agent_id
            or (
                existing_record.strategy_agent_id
                if existing_record is not None
                else configured_default_strategy_agent_id()
            )
        )
        default_options = dict(provider_options_payload.get("default_options") or {})
        knowledge_approval_policy = (
            payload.knowledge_approval_policy
            or (
                existing_record.knowledge_approval_policy
                if existing_record is not None
                else str(
                    default_options.get("knowledge_approval_policy")
                    or "agent_decides"
                )
            )
        )
        base_branch_context = (
            existing_record.branch_context
            if existing_record is not None
            else SessionBranchContext()
        )
        requested_scope_id = (
            payload.knowledge_scope_id
            if "knowledge_scope_id" in payload.model_fields_set
            else base_branch_context.knowledge_scope_id
        )
        scope_label = "全部知识"
        if requested_scope_id is not None:
            try:
                scope_folder = explorer.get_folder(requested_scope_id)
            except KeyError as exc:
                raise HTTPException(status_code=400, detail="Unknown knowledge scope") from exc
            if scope_folder.scope != "knowledge":
                raise HTTPException(status_code=400, detail="Invalid knowledge scope")
            scope_label = scope_folder.path_cached.strip("/") or scope_folder.name
        scope_changed = requested_scope_id != base_branch_context.knowledge_scope_id
        requested_branch_context = replace(
            base_branch_context,
            knowledge_scope_id=requested_scope_id,
            active_node_ids=[] if scope_changed else list(base_branch_context.active_node_ids),
            summary_node_ids=[] if scope_changed else list(base_branch_context.summary_node_ids),
            active_symbols={} if scope_changed else dict(base_branch_context.active_symbols),
        )
        result = _answer_question(
            question=payload.question,
            session_id=session_id,
            provider_profile=provider_profile,
            branch_context=requested_branch_context,
            answer_style_id=payload.answer_style_id,
            strategy_agent_id=strategy_agent_id,
            knowledge_approval_policy=knowledge_approval_policy,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
        )

        user_message = SessionMessage(role="user", content=payload.question)
        orchestration_plan = result.orchestration_plan or result.action.orchestration_plan
        if orchestration_plan is not None:
            orchestration_plan.knowledge_scope_id = requested_scope_id
            orchestration_plan.knowledge_scope_label = scope_label
        assistant_message = SessionMessage(
            role="assistant",
            content=result.answer.assistant_text,
            assistant_context=SessionAssistantContext(
                action_type=result.action.action_type,
                referenced_node_ids=list(result.answer.references),
                anchors=list(result.answer.anchors),
                orchestration_plan=orchestration_plan,
                state_items=list(result.state_items),
            ),
        )
        branch_context = (
            result.branch_context
            if result.branch_context is not None
            else (
                existing_record.branch_context
                if existing_record is not None
                else SessionBranchContext()
            )
        )
        generated_title = None
        generated_category = None
        if (
            existing_record is None
            or not existing_record.title
            or not existing_record.icon
        ):
            generated_title, generated_category = _generate_session_identity(
                session_id=session_id,
                question=payload.question,
                answer=result.answer.assistant_text,
                provider_profile=provider_profile,
                credential_registry=credentials,
                provider_options_payload=provider_options.load(),
                provider_gateway=resolved_provider_gateway,
            )
        title = (
            existing_record.title
            if existing_record is not None and existing_record.title
            else generated_title or payload.question.strip()
        )
        icon = (
            existing_record.icon
            if existing_record is not None and existing_record.icon
            else generated_category or DEFAULT_SESSION_CATEGORY
        )

        if existing_record is None:
            sessions.save_record(
                SessionRecord(
                    session_id=session_id,
                    title=title,
                    icon=icon,
                    conversation_model=conversation_model,
                    provider_profile=provider_profile,
                    default_answer_style_id=None,
                    strategy_agent_id=strategy_agent_id,
                    knowledge_approval_policy=knowledge_approval_policy,
                    branch_context=branch_context,
                    messages=[],
                )
            )
        sessions.save_working_turn(
            session_id,
            SessionWorkingTurn(
                state="awaiting_answer",
                user_message=user_message,
                assistant_message=assistant_message,
            ),
        )
        sessions.append_messages(
            session_id,
            [user_message, assistant_message],
            branch_context=branch_context,
            title=title,
            icon=icon,
            conversation_model=conversation_model,
            provider_profile=provider_profile,
            strategy_agent_id=strategy_agent_id,
            knowledge_approval_policy=knowledge_approval_policy,
        )
        sessions.save_working_turn(session_id, None)
        if result.answer.knowledge_job_id is not None:
            resolved_knowledge_job_repository.attach_source_message(
                result.answer.knowledge_job_id,
                session_id=session_id,
                source_message_id=assistant_message.message_id,
            )

        saved_record = sessions.load_record(session_id)
        if saved_record is None:
            raise HTTPException(status_code=500, detail="Session persistence failed")

        session_schema = _record_to_session_schema(saved_record)

        return AskResponseSchema.model_validate(
            {
                "action": {
                    "action_type": result.action.action_type,
                    "selected_node_ids": result.action.selected_node_ids,
                    "draft_requests": [
                        {
                            "title": draft.title,
                            "draft_type": draft.draft_type,
                            "reason": draft.reason,
                        }
                        for draft in result.action.draft_requests
                    ],
                    "user_visible_reason": result.action.user_visible_reason,
                },
                "answer": {
                    "summary": result.answer.summary,
                    "detail": result.answer.detail,
                    "references": result.answer.references,
                    "anchors": [
                        _answer_anchor_to_schema(anchor).model_dump()
                        for anchor in result.answer.anchors
                    ],
                    "knowledge_job_id": result.answer.knowledge_job_id,
                    "symbols": result.answer.symbols,
                    "symbol_conflicts": result.answer.symbol_conflicts,
                    "assistant_text": result.answer.assistant_text,
                },
                "drafts": [
                    {
                        "title": draft.title,
                        "draft_type": draft.draft_type,
                        "reason": draft.reason,
                    }
                    for draft in result.drafts
                ],
                "created_node_ids": result.created_node_ids,
                "session": session_schema.model_dump(),
            }
        )

    @app.post("/api/ask", response_model=AskResponseSchema)
    def ask(payload: AskRequestSchema) -> AskResponseSchema:
        return _ask_response(payload)

    @app.post("/api/ask/stream")
    def ask_stream(payload: AskRequestSchema) -> StreamingResponse:
        def event_stream():
            queue: Queue[tuple[str, object] | None] = Queue()
            state: dict[str, object] = {}

            def worker() -> None:
                try:
                    response = _ask_response(
                        payload,
                        stream_callback=lambda delta: queue.put(("chunk", delta)),
                        progress_callback=lambda event: queue.put(("progress", event)),
                    )
                    state["response"] = response
                except HTTPException as exc:
                    state["error"] = exc
                finally:
                    queue.put(None)

            Thread(target=worker, daemon=True).start()

            while True:
                queued_event = queue.get()
                if queued_event is None:
                    break
                event_name, event_payload = queued_event
                if event_name == "chunk":
                    yield _sse_event("chunk", {"delta": event_payload})
                elif isinstance(event_payload, dict):
                    yield _sse_event("progress", event_payload)

            error = state.get("error")
            if isinstance(error, HTTPException):
                yield _sse_event(
                    "error",
                    {"status_code": error.status_code, "detail": error.detail},
                )
                return

            response = state.get("response")
            if isinstance(response, AskResponseSchema):
                yield _sse_event("final", response.model_dump())
                return
            yield _sse_event(
                "error",
                {"status_code": 500, "detail": "Stream response not available"},
            )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def _sync_knowledge_job_to_session(job: object) -> None:
        session_id = getattr(job, "session_id", None)
        source_message_id = getattr(job, "source_message_id", None)
        if not isinstance(session_id, str) or not isinstance(source_message_id, str):
            return
        status = getattr(job, "status", "")
        if status not in {"completed", "failed"}:
            return
        _merge_job_anchors_into_session_message(
            session_id=session_id,
            message_id=source_message_id,
            anchors=list(getattr(job, "anchors", [])),
            state="ready" if status == "completed" else "failed",
            error_message=getattr(job, "error_message", None),
        )

    def _merge_job_anchors_into_session_message(
        *,
        session_id: str,
        message_id: str,
        anchors: list[AnswerAnchor],
        state: str,
        error_message: str | None = None,
    ) -> None:
        record = sessions.load_record(session_id)
        if record is None:
            return
        updated_messages: list[SessionMessage] = []
        changed = False
        for message in record.messages:
            if message.message_id != message_id:
                updated_messages.append(message)
                continue
            existing_by_id = {
                anchor.anchor_id: anchor
                for anchor in message.assistant_context.anchors
            }
            incoming_by_id = {anchor.anchor_id: anchor for anchor in anchors}
            anchor_order = [
                anchor.anchor_id for anchor in message.assistant_context.anchors
            ]
            anchor_order.extend(
                anchor.anchor_id
                for anchor in anchors
                if anchor.anchor_id not in existing_by_id
            )
            merged_anchors = [
                incoming_by_id[anchor_id]
                if anchor_id in incoming_by_id
                else existing_by_id[anchor_id]
                for anchor_id in anchor_order
            ]

            state_items = list(message.assistant_context.state_items)
            for anchor in anchors:
                item_state = anchor.status if anchor.status in {"ready", "failed"} else state
                for index, item in enumerate(state_items):
                    if item.title != anchor.label:
                        continue
                    state_items[index] = AgentStateItem(
                        item_id=item.item_id,
                        kind=item.kind,
                        state=item_state,
                        title=item.title,
                        reason=item.reason,
                        source_message_id=item.source_message_id or message_id,
                        node_id=anchor.node_id,
                        error_message=error_message if item_state == "failed" else None,
                    )
                    break
                else:
                    state_items.append(
                        AgentStateItem(
                            item_id=f"draft-{_slugify(anchor.label)}",
                            kind="knowledge_draft",
                            state=item_state,
                            title=anchor.label,
                            reason="Accepted suggested draft.",
                            source_message_id=message_id,
                            node_id=anchor.node_id,
                            error_message=error_message if item_state == "failed" else None,
                        )
                    )

            updated_context = SessionAssistantContext(
                action_type=message.assistant_context.action_type,
                referenced_node_ids=list(message.assistant_context.referenced_node_ids),
                anchors=merged_anchors,
                symbol_conflicts=list(message.assistant_context.symbol_conflicts),
                alignment_notes=list(message.assistant_context.alignment_notes),
                compact_summary=message.assistant_context.compact_summary,
                orchestration_plan=message.assistant_context.orchestration_plan,
                state_items=state_items,
            )
            if updated_context == message.assistant_context:
                updated_messages.append(message)
                continue
            updated_messages.append(
                replace(message, assistant_context=updated_context)
            )
            changed = True
        if changed:
            sessions.save_record(replace(record, messages=updated_messages))

    def _set_knowledge_authorization_status(
        *,
        session_id: str,
        message_id: str,
        authorization_status: str,
    ) -> SessionRecord:
        record = sessions.load_record(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        updated_messages: list[SessionMessage] = []
        changed = False
        for message in record.messages:
            if message.message_id != message_id:
                updated_messages.append(message)
                continue
            plan = message.assistant_context.orchestration_plan
            if message.role != "assistant" or plan is None or not plan.candidate_drafts:
                raise HTTPException(status_code=409, detail="No knowledge approval is pending")
            authorization = replace(
                plan.authorization,
                status=authorization_status,
            )
            state_items = list(message.assistant_context.state_items)
            if authorization_status == "denied":
                draft_titles = {draft.title for draft in plan.candidate_drafts}
                state_items = [
                    replace(item, state="dismissed")
                    if item.kind == "knowledge_draft" and item.title in draft_titles
                    else item
                    for item in state_items
                ]
            updated_context = replace(
                message.assistant_context,
                orchestration_plan=replace(plan, authorization=authorization),
                state_items=state_items,
            )
            updated_messages.append(replace(message, assistant_context=updated_context))
            changed = True
        if not changed:
            raise HTTPException(status_code=404, detail="Assistant message not found")
        updated_record = replace(record, messages=updated_messages)
        sessions.save_record(updated_record)
        return updated_record

    def _reconcile_ready_knowledge_items(record: SessionRecord) -> SessionRecord:
        active_jobs = {
            (
                job.source_message_id,
                draft.title.strip().casefold(),
            )
            for job in resolved_knowledge_job_repository.list_jobs(record.session_id)
            if job.status in {"queued", "running", "writing"}
            for draft in job.draft_requests
        }
        ready_nodes_by_title = {
            node.title.strip().casefold(): node
            for node in knowledge_repository.list_nodes()
            if node.status == "ready" and node.source == record.session_id
        }
        reconciled = False
        for message in record.messages:
            ready_anchors: list[AnswerAnchor] = []
            for item in message.assistant_context.state_items:
                if item.kind != "knowledge_draft" or item.state not in {
                    "pending",
                    "queued",
                    "running",
                    "writing",
                }:
                    continue
                title_key = item.title.strip().casefold()
                if (message.message_id, title_key) in active_jobs:
                    continue
                node = ready_nodes_by_title.get(title_key)
                if node is None:
                    continue
                existing_anchor = next(
                    (
                        anchor
                        for anchor in message.assistant_context.anchors
                        if anchor.label.strip().casefold() == title_key
                    ),
                    None,
                )
                ready_anchors.append(
                    AnswerAnchor(
                        anchor_id=(
                            existing_anchor.anchor_id
                            if existing_anchor is not None
                            else node.id
                        ),
                        label=item.title,
                        status="ready",
                        node_id=node.id,
                    )
                )
            if not ready_anchors:
                continue
            _merge_job_anchors_into_session_message(
                session_id=record.session_id,
                message_id=message.message_id,
                anchors=ready_anchors,
                state="ready",
            )
            reconciled = True
        if not reconciled:
            return record
        return sessions.load_record(record.session_id) or record

    resolved_knowledge_job_repository.add_terminal_listener(
        _sync_knowledge_job_to_session
    )

    @app.get("/api/knowledge-jobs/{job_id}", response_model=KnowledgeJobSchema)
    def get_knowledge_job(job_id: str) -> KnowledgeJobSchema:
        job = resolved_knowledge_job_repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Knowledge job not found")
        _sync_knowledge_job_to_session(job)
        return KnowledgeJobSchema.model_validate(
            {
                "job_id": job.job_id,
                "status": job.status,
                "anchors": [
                    _answer_anchor_to_schema(anchor).model_dump()
                    for anchor in job.anchors
                ],
                "error_message": job.error_message,
            }
        )

    @app.post(
        "/api/selection/knowledge-drafts",
        response_model=KnowledgeJobSchema,
    )
    def create_selection_knowledge_draft(
        payload: SelectionKnowledgeDraftRequestSchema,
    ) -> KnowledgeJobSchema:
        selected_text = (payload.selected_text or "").strip()
        if not selected_text:
            raise HTTPException(status_code=400, detail="selected_text is required")

        prompt_kind = (payload.prompt_kind or "").strip()
        draft_type_by_prompt_kind = {
            "definition": "definition",
            "intuition_node": "atomic",
            "example": "atomic",
            "proof": "proof",
        }
        draft_type = draft_type_by_prompt_kind.get(prompt_kind)
        if draft_type is None:
            raise HTTPException(status_code=400, detail="Unsupported prompt_kind")

        title = _selection_draft_title_seed(selected_text, prompt_kind)
        source_type = (payload.source.type or "").strip()
        if source_type not in {"chat-message", "knowledge-node"}:
            raise HTTPException(status_code=400, detail="Unsupported source type")

        draft_requests = [
            PendingDraftRequest(
                title=title,
                draft_type=draft_type,
                reason=(
                    f"Draft a {prompt_kind.replace('_', ' ')} from the selected text."
                ),
            )
        ]
        selected_node_ids: list[str] = []
        session_id: str | None = None
        source_message_id: str | None = None
        symbol_constraints: dict[str, str] | None = None
        provider_profile = None

        if source_type == "knowledge-node":
            node_id = (payload.source.node_id or "").strip()
            if not node_id:
                raise HTTPException(
                    status_code=400,
                    detail="node_id is required for knowledge-node sources",
                )
            try:
                node = knowledge_repository.get_node(node_id)
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=404, detail="Knowledge node not found"
                ) from exc
            selected_node_ids = [node.id]
            selection = _default_model_selection_to_model_selection(
                payload.conversation_model
            )
            provider_profile = _resolve_provider_profile_from_selection(
                selection=selection,
                credential_registry=credentials,
                provider_options_payload=provider_options.load(),
            )
        else:
            session_id_value = (payload.source.session_id or "").strip()
            if not session_id_value:
                raise HTTPException(
                    status_code=400,
                    detail="session_id is required for chat-message sources",
                )
            message_id_value = (payload.source.message_id or "").strip()
            if not message_id_value:
                raise HTTPException(
                    status_code=400,
                    detail="message_id is required for chat-message sources",
                )
            record = sessions.load_record(session_id_value)
            if record is None:
                raise HTTPException(status_code=404, detail="Session not found")
            message = next(
                (
                    item
                    for item in record.messages
                    if item.message_id == message_id_value
                ),
                None,
            )
            if message is None:
                raise HTTPException(
                    status_code=404, detail="Session message not found"
                )
            session_id = record.session_id
            source_message_id = message.message_id
            selected_node_ids = list(message.assistant_context.referenced_node_ids)
            symbol_constraints = dict(record.branch_context.active_symbols)
            selection = _default_model_selection_to_model_selection(
                payload.conversation_model
            )
            provider_profile = (
                _resolve_provider_profile_from_selection(
                    selection=selection,
                    credential_registry=credentials,
                    provider_options_payload=provider_options.load(),
                )
                if selection is not None
                else record.provider_profile
            )

        if provider_profile is None:
            raise HTTPException(
                status_code=503,
                detail="A provider profile is required before compiling selection knowledge drafts",
            )

        job = resolved_knowledge_job_repository.submit_compile_job(
            session_id=session_id,
            source_message_id=source_message_id,
            question=selected_text,
            selection_source_text=selected_text,
            anchors=[],
            selected_node_ids=selected_node_ids,
            draft_requests=draft_requests,
            provider_profile=provider_profile,
            symbol_constraints=symbol_constraints,
        )
        refreshed = resolved_knowledge_job_repository.get_job(job.job_id) or job
        return KnowledgeJobSchema.model_validate(
            {
                "job_id": refreshed.job_id,
                "status": refreshed.status,
                "anchors": [
                    _answer_anchor_to_schema(anchor).model_dump()
                    for anchor in refreshed.anchors
                ],
                "error_message": refreshed.error_message,
            }
        )

    @app.post(
        "/api/sessions/{session_id}/messages/{message_id}/suggested-drafts/compile",
        response_model=KnowledgeJobSchema,
    )
    def compile_suggested_drafts(
        session_id: str,
        message_id: str,
        payload: CompileSuggestedDraftsRequestSchema,
    ) -> KnowledgeJobSchema:
        record = sessions.load_record(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        message_index = next(
            (
                index
                for index, item in enumerate(record.messages)
                if item.message_id == message_id
            ),
            None,
        )
        message = record.messages[message_index] if message_index is not None else None
        if message is None or message.role != "assistant":
            raise HTTPException(status_code=404, detail="Assistant message not found")
        plan = message.assistant_context.orchestration_plan
        if plan is None or not plan.candidate_drafts:
            raise HTTPException(status_code=409, detail="No suggested drafts to compile")
        if len(set(payload.draft_indexes)) != len(payload.draft_indexes):
            raise HTTPException(status_code=400, detail="Duplicate draft indexes")
        if any(index < 0 or index >= len(plan.candidate_drafts) for index in payload.draft_indexes):
            raise HTTPException(status_code=400, detail="Draft index out of range")
        if plan.authorization.status == "denied":
            raise HTTPException(status_code=409, detail="Knowledge write was denied")

        _set_knowledge_authorization_status(
            session_id=session_id,
            message_id=message_id,
            authorization_status="approved",
        )

        selected_candidates = [plan.candidate_drafts[index] for index in payload.draft_indexes]
        source_question = next(
            (
                item.content
                for item in reversed(record.messages[:message_index])
                if item.role == "user"
            ),
            message.content,
        )
        draft_requests = [
            PendingDraftRequest(
                title=candidate.title,
                draft_type=candidate.draft_type,
                reason=candidate.reason,
            )
            for candidate in selected_candidates
        ]
        anchors = [
            AnswerAnchor(
                anchor_id=_slugify(candidate.title),
                label=candidate.title,
                status="pending",
                node_id=None,
            )
            for candidate in selected_candidates
        ]
        provider_profile = (
            record.provider_profile
            or _resolve_provider_profile_from_selection(
                selection=record.conversation_model,
                credential_registry=credentials,
                provider_options_payload=provider_options.load(),
            )
        )
        _merge_job_anchors_into_session_message(
            session_id=session_id,
            message_id=message_id,
            anchors=anchors,
            state="queued",
        )
        job = resolved_knowledge_job_repository.submit_compile_job(
            session_id=session_id,
            source_message_id=message_id,
            question=source_question,
            anchors=anchors,
            selected_node_ids=list(message.assistant_context.referenced_node_ids),
            draft_requests=draft_requests,
            provider_profile=provider_profile,
            symbol_constraints=dict(record.branch_context.active_symbols),
        )
        refreshed = resolved_knowledge_job_repository.get_job(job.job_id) or job
        return KnowledgeJobSchema.model_validate(
            {
                "job_id": refreshed.job_id,
                "status": refreshed.status,
                "anchors": [
                    _answer_anchor_to_schema(anchor).model_dump()
                    for anchor in refreshed.anchors
                ],
                "error_message": refreshed.error_message,
            }
        )

    @app.post(
        "/api/sessions/{session_id}/messages/{message_id}/suggested-drafts/reject",
        response_model=SessionSchema,
    )
    def reject_suggested_drafts(
        session_id: str,
        message_id: str,
    ) -> SessionSchema:
        record = sessions.load_record(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        message = next(
            (item for item in record.messages if item.message_id == message_id),
            None,
        )
        if message is None or message.role != "assistant":
            raise HTTPException(status_code=404, detail="Assistant message not found")
        plan = message.assistant_context.orchestration_plan
        if plan is None or not plan.candidate_drafts:
            raise HTTPException(status_code=409, detail="No suggested drafts to reject")
        if plan.authorization.status not in {"pending", "not_required"}:
            raise HTTPException(status_code=409, detail="Knowledge approval is not pending")
        updated_record = _set_knowledge_authorization_status(
            session_id=session_id,
            message_id=message_id,
            authorization_status="denied",
        )
        return _record_to_session_schema(updated_record)

    @app.post(
        "/api/sessions/{session_id}/messages/{message_id}/regenerate",
        response_model=SessionSchema,
    )
    def regenerate_session_message(
        session_id: str, message_id: str, payload: RegenerateRequestSchema
    ) -> SessionSchema:
        record = sessions.load_local_record(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if not record.messages:
            raise HTTPException(
                status_code=409,
                detail="Only the latest assistant message can be regenerated",
            )
        latest_message = record.messages[-1]
        if latest_message.role != "assistant" or latest_message.message_id != message_id:
            raise HTTPException(
                status_code=409,
                detail="Only the latest assistant message can be regenerated",
            )
        if len(record.messages) < 2 or record.messages[-2].role != "user":
            raise HTTPException(
                status_code=409,
                detail="Only the latest assistant message can be regenerated",
            )

        user_message = record.messages[-2]
        provider_profile = (
            record.provider_profile
            or _resolve_provider_profile_from_selection(
                selection=record.conversation_model,
                credential_registry=credentials,
                provider_options_payload=provider_options.load(),
            )
        )
        result = _answer_question(
            question=user_message.content,
            session_id=record.session_id,
            provider_profile=provider_profile,
            branch_context=record.branch_context,
            answer_style_id=payload.answer_style_id,
            strategy_agent_id=record.strategy_agent_id,
            knowledge_approval_policy=record.knowledge_approval_policy,
        )
        orchestration_plan = result.orchestration_plan or result.action.orchestration_plan
        assistant_message = SessionMessage(
            role="assistant",
            content=result.answer.assistant_text,
            assistant_context=SessionAssistantContext(
                action_type=result.action.action_type,
                referenced_node_ids=list(result.answer.references),
                anchors=list(result.answer.anchors),
                orchestration_plan=orchestration_plan,
                state_items=list(result.state_items),
            ),
        )
        if result.answer.knowledge_job_id is not None:
            resolved_knowledge_job_repository.attach_source_message(
                result.answer.knowledge_job_id,
                session_id=record.session_id,
                source_message_id=assistant_message.message_id,
            )
        branch_context = (
            result.branch_context
            if result.branch_context is not None
            else record.branch_context
        )
        updated = SessionRecord(
            session_id=record.session_id,
            title=record.title,
            icon=record.icon,
            conversation_model=record.conversation_model,
            provider_profile=provider_profile,
            default_answer_style_id=record.default_answer_style_id,
            strategy_agent_id=record.strategy_agent_id,
            knowledge_approval_policy=record.knowledge_approval_policy,
            branch_context=branch_context,
            messages=[*record.messages[:-1], assistant_message],
            created_at=record.created_at,
        )
        sessions.save_record(updated)
        saved_record = sessions.load_record(session_id)
        if saved_record is None:
            raise HTTPException(status_code=500, detail="Session persistence failed")
        return _record_to_session_schema(saved_record)

    @app.get("/api/outline", response_model=OutlineResponseSchema)
    def outline() -> OutlineResponseSchema:
        nodes = knowledge_repository.list_nodes()
        return OutlineResponseSchema.model_validate(
            {
                "nodes": [
                    {
                        "id": node.id,
                        "title": node.title,
                        "type": node.type,
                        "summary": node.summary,
                        "parent_id": node.parent_id,
                        "status": node.status,
                    }
                    for node in nodes
                ]
            }
        )

    def _knowledge_explorer_items() -> list[dict[str, object]]:
        source_icons: dict[str, str] = {}

        def inherited_icon(source_session_id: str) -> str:
            if source_session_id not in source_icons:
                source_record = sessions.load_record(source_session_id)
                source_icons[source_session_id] = (
                    source_record.icon
                    if source_record is not None and source_record.icon
                    else DEFAULT_SESSION_CATEGORY
                )
            return source_icons[source_session_id]

        return [
            {
                "item_type": "knowledge_node",
                "item_id": node.id,
                "id": node.id,
                "title": node.title,
                "icon": inherited_icon(node.source),
                "type": node.type,
                "summary": node.summary,
                "parent_id": node.parent_id,
                "status": node.status,
            }
            for node in knowledge_repository.list_nodes()
        ]

    @app.get("/api/nodes/{node_id}", response_model=NodeResponseSchema)
    def get_node(node_id: str) -> NodeResponseSchema:
        try:
            node = knowledge_repository.get_node(node_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Node not found") from exc
        incoming_references = knowledge_repository.list_incoming_references(node_id)
        related_session_ids = knowledge_repository.list_related_session_ids(node_id)
        return NodeResponseSchema.model_validate(
            {
                "node": {
                    "id": node.id,
                    "title": node.title,
                    "type": node.type,
                    "summary": node.summary,
                    "detail": node.detail,
                    "parent_id": node.parent_id,
                    "source": node.source,
                    "references": [
                        {"node_id": ref.node_id, "reason": ref.reason}
                        for ref in node.references
                    ],
                    "incoming_references": [
                        {"node_id": ref.node_id, "reason": ref.reason}
                        for ref in incoming_references
                    ],
                    "related_session_ids": related_session_ids,
                    "references_display": [
                        _display_reference_payload(knowledge_repository, ref)
                        for ref in node.references
                    ],
                    "incoming_references_display": [
                        _display_reference_payload(knowledge_repository, ref)
                        for ref in incoming_references
                    ],
                    "related_discussions": [
                        _related_discussion_payload(sessions, session_id)
                        for session_id in related_session_ids
                    ],
                    "status": node.status,
                    "symbols": node.symbols,
                    "symbol_scopes": node.symbol_scopes,
                    "revision": node.revision,
                    "updated_at": node.updated_at,
                }
            }
        )

    @app.patch("/api/nodes/{node_id}", response_model=NodeResponseSchema)
    def update_node(
        node_id: str,
        payload: KnowledgeNodeUpdateSchema,
    ) -> NodeResponseSchema:
        try:
            node = knowledge_repository.get_node(node_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Node not found") from exc
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No knowledge changes supplied")
        knowledge_repository.save_node(
            replace(
                node,
                **updates,
                revision=node.revision + 1,
                updated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
        )
        return get_node(node_id)

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> SessionSchema:
        record = sessions.load_record(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        record = _reconcile_ready_knowledge_items(record)
        record = _hydrated_record_provider_profile(
            record,
            credential_registry=credentials,
            provider_options_payload=provider_options.load(),
        )
        return _record_to_session_schema(record)

    @app.patch("/api/sessions/{session_id}", response_model=SessionSchema)
    def update_session(
        session_id: str,
        payload: SessionUpdateSchema,
    ) -> SessionSchema:
        record = sessions.load_record(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        conversation_model = (
            _default_model_selection_to_model_selection(payload.conversation_model)
            if payload.conversation_model is not None
            else record.conversation_model
        )
        provider_profile = (
            _resolve_provider_profile_from_selection(
                selection=conversation_model,
                credential_registry=credentials,
                provider_options_payload=provider_options.load(),
            )
            if payload.conversation_model is not None
            else record.provider_profile
        )
        if payload.conversation_model is not None and provider_profile is None:
            raise HTTPException(
                status_code=400,
                detail="Conversation model does not resolve to a configured credential",
            )
        updated = sessions.update_record(
            session_id,
            title=payload.title if payload.title is not None else record.title,
            icon=payload.icon if payload.icon is not None else record.icon,
            conversation_model=conversation_model,
            provider_profile=provider_profile,
            knowledge_approval_policy=(
                payload.knowledge_approval_policy
                if payload.knowledge_approval_policy is not None
                else record.knowledge_approval_policy
            ),
        )
        return _record_to_session_schema(updated)

    @app.delete("/api/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_session(session_id: str) -> Response:
        record = sessions.load_record(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        records = sessions.list_recent_records()
        if any(
            candidate.branch_context.parent_session_id == session_id
            for candidate in records
        ):
            raise HTTPException(
                status_code=409,
                detail="Cannot delete a conversation that still has child branches",
            )
        sessions.delete_record(session_id)
        explorer.remove_item(item_type="session", item_id=session_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/api/sessions/{session_id}/fork", response_model=SessionSchema)
    def fork_session(
        session_id: str, payload: SessionForkRequestSchema
    ) -> SessionSchema:
        parent_record = sessions.load_record(session_id)
        if parent_record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        fork_anchor = payload.fork_anchor
        if fork_anchor.type == "message":
            if fork_anchor.message_id is None:
                raise HTTPException(status_code=400, detail="Message fork anchor requires message_id")
            if sessions.has_working_message_id(session_id, fork_anchor.message_id):
                raise HTTPException(status_code=409, detail="Cannot fork from mutable working turn")
            if sessions.find_committed_message(session_id, fork_anchor.message_id) is None:
                raise HTTPException(status_code=404, detail="Fork anchor message not found")

        branch_context = _fork_branch_context(
            repository=knowledge_repository,
            parent_record=parent_record,
            payload=payload,
        )
        child_session_id = f"{session_id}-fork-{uuid4().hex[:8]}"
        child_record = SessionRecord(
            session_id=child_session_id,
            title=f"{parent_record.title} (fork)" if parent_record.title else None,
            icon=parent_record.icon,
            conversation_model=parent_record.conversation_model,
            provider_profile=parent_record.provider_profile,
            default_answer_style_id=parent_record.default_answer_style_id,
            strategy_agent_id=parent_record.strategy_agent_id,
            knowledge_approval_policy=parent_record.knowledge_approval_policy,
            branch_context=branch_context,
            messages=[],
        )
        sessions.save_record(child_record)
        parent_location = explorer.find_location("session", session_id)
        if parent_location is not None:
            explorer.ensure_item_location(
                item_type="session",
                item_id=child_session_id,
                folder_id=parent_location.folder_id,
                location_source="system",
            )
        hydrated_child_record = sessions.load_record(child_session_id)
        if hydrated_child_record is None:
            raise HTTPException(status_code=500, detail="Session persistence failed")
        return _record_to_session_schema(hydrated_child_record)

    @app.post("/api/sessions/{session_id}/compact", response_model=SessionSchema)
    def compact_session(
        session_id: str, payload: CompactRequestSchema
    ) -> SessionSchema:
        record = sessions.load_record(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        compacted_record = _compact_session_record(
            repository=knowledge_repository,
            record=record,
            payload=payload,
        )
        updated = sessions.append_messages(
            session_id,
            [compacted_record.messages[-1]],
            branch_context=compacted_record.branch_context,
        )
        return _record_to_session_schema(updated)

    @app.get("/api/sessions", response_model=SessionsListResponseSchema)
    def list_sessions() -> SessionsListResponseSchema:
        records = sessions.list_recent_records()
        records = [
            _hydrated_record_provider_profile(
                record,
                credential_registry=credentials,
                provider_options_payload=provider_options.load(),
            )
            for record in records
        ]
        tree_metadata = _session_tree_metadata(records)
        return SessionsListResponseSchema.model_validate(
            {
                "sessions": [
                    SessionListItemSchema(
                        session_id=record.session_id,
                        title=record.title,
                        icon=record.icon,
                        conversation_model=_model_selection_to_schema(
                            record.conversation_model
                        ),
                        provider_profile=_provider_profile_to_schema(
                            record.provider_profile
                        ),
                        default_answer_style_id=record.default_answer_style_id,
                        strategy_agent_id=record.strategy_agent_id,
                        knowledge_approval_policy=record.knowledge_approval_policy,
                        knowledge_scope_id=record.branch_context.knowledge_scope_id,
                        branch=_branch_context_to_schema(
                            record.branch_context
                        ),
                        message_count=record.message_count,
                        last_message=(
                            _session_message_to_schema(record.last_message)
                            if record.last_message is not None
                            else None
                        ),
                        branch_depth=tree_metadata.get(record.session_id, {}).get(
                            "branch_depth", 0
                        ),
                        child_session_ids=tree_metadata.get(record.session_id, {}).get(
                            "child_session_ids", []
                        ),
                    ).model_dump()
                    for record in records
                ]
            }
        )

    def _session_explorer_items() -> list[dict[str, object]]:
        records = sessions.list_recent_records()
        tree_metadata = _session_tree_metadata(records)
        return [
            {
                "item_type": "session",
                "item_id": record.session_id,
                "session_id": record.session_id,
                "title": record.title,
                "icon": record.icon,
                "message_count": record.message_count,
                "branch": _branch_context_to_schema(record.branch_context).model_dump(),
                "branch_depth": tree_metadata.get(record.session_id, {}).get(
                    "branch_depth", 0
                ),
                "child_session_ids": tree_metadata.get(record.session_id, {}).get(
                    "child_session_ids", []
                ),
            }
            for record in records
        ]

    def _ensure_explorer_item_exists(item_type: str, item_id: str) -> None:
        if item_type == "session":
            if sessions.load_record(item_id) is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return
        if item_type == "knowledge_node":
            try:
                knowledge_repository.get_node(item_id)
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Knowledge note not found") from exc

    @app.get("/api/explorer/sessions", response_model=ExplorerTreeResponseSchema)
    def get_sessions_explorer() -> ExplorerTreeResponseSchema:
        return ExplorerTreeResponseSchema.model_validate(
            {
                "scope": "sessions",
                "tree": explorer.build_tree(
                    scope="sessions",
                    items=_session_explorer_items(),
                ),
            }
        )

    @app.get("/api/explorer/knowledge", response_model=ExplorerTreeResponseSchema)
    def get_knowledge_explorer() -> ExplorerTreeResponseSchema:
        return ExplorerTreeResponseSchema.model_validate(
            {
                "scope": "knowledge",
                "tree": explorer.build_tree(
                    scope="knowledge",
                    items=_knowledge_explorer_items(),
                ),
            }
        )

    @app.post(
        "/api/explorer/knowledge/organize",
        response_model=ExplorerOrganizeResponseSchema,
    )
    def organize_knowledge_explorer() -> ExplorerOrganizeResponseSchema:
        folder_names = {
            "definition": "Definitions",
            "theorem": "Theorems",
            "lemma": "Theorems",
            "proposition": "Theorems",
            "corollary": "Theorems",
            "proof": "Proofs & Derivations",
            "derivation": "Proofs & Derivations",
            "example": "Examples & Applications",
            "application": "Examples & Applications",
        }
        folder_sort_orders = {
            "Definitions": 1000,
            "Theorems": 2000,
            "Proofs & Derivations": 3000,
            "Examples & Applications": 4000,
            "Concepts & Notes": 5000,
        }
        folders_created = 0
        organized_count = 0
        folders_by_name: dict[str, ExplorerFolder] = {}
        for item in _knowledge_explorer_items():
            item_id = str(item["item_id"])
            location = explorer.find_location("knowledge_node", item_id)
            if location is not None and (
                location.folder_id is not None or location.user_locked
            ):
                continue
            node_type = str(item.get("type") or "").strip().lower()
            folder_name = folder_names.get(node_type, "Concepts & Notes")
            folder = folders_by_name.get(folder_name)
            if folder is None:
                folder = explorer.find_folder(
                    scope="knowledge",
                    name=folder_name,
                    parent_folder_id=None,
                )
                if folder is None:
                    folder = explorer.create_folder(
                        scope="knowledge",
                        name=folder_name,
                        parent_folder_id=None,
                        sort_order=folder_sort_orders[folder_name],
                    )
                    folders_created += 1
                folders_by_name[folder_name] = folder
            explorer.move_item(
                item_type="knowledge_node",
                item_id=item_id,
                folder_id=folder.folder_id,
                sort_order=1000,
                location_source="agent",
            )
            organized_count += 1
        return ExplorerOrganizeResponseSchema(
            scope="knowledge",
            organized_count=organized_count,
            folders_created=folders_created,
        )

    @app.post("/api/explorer/folders", response_model=ExplorerFolderResponseSchema)
    def create_explorer_folder(
        payload: ExplorerFolderCreateSchema,
    ) -> ExplorerFolderResponseSchema:
        try:
            folder = explorer.create_folder(
                scope=payload.scope,
                name=payload.name,
                parent_folder_id=payload.parent_folder_id,
            )
        except ExplorerFolderConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Parent folder not found") from exc
        except (ExplorerInvalidMoveError, ExplorerError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExplorerFolderResponseSchema.model_validate(
            {"folder": folder.as_dict()}
        )

    @app.patch(
        "/api/explorer/folders/{folder_id}",
        response_model=ExplorerFolderResponseSchema,
    )
    def rename_explorer_folder(
        folder_id: str,
        payload: ExplorerFolderUpdateSchema,
    ) -> ExplorerFolderResponseSchema:
        try:
            folder = explorer.rename_folder(folder_id, payload.name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Folder not found") from exc
        except ExplorerFolderConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ExplorerInvalidMoveError, ExplorerError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExplorerFolderResponseSchema.model_validate(
            {"folder": folder.as_dict()}
        )

    @app.delete("/api/explorer/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_explorer_folder(folder_id: str) -> Response:
        try:
            explorer.delete_folder(folder_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Folder not found") from exc
        except ExplorerInvalidMoveError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.patch(
        "/api/explorer/items/{item_type}/{item_id}/location",
        response_model=ExplorerItemLocationResponseSchema,
    )
    def move_explorer_item(
        item_type: str,
        item_id: str,
        payload: ExplorerItemLocationUpdateSchema,
    ) -> ExplorerItemLocationResponseSchema:
        _ensure_explorer_item_exists(item_type, item_id)
        try:
            location = explorer.move_item(
                item_type=item_type,
                item_id=item_id,
                folder_id=payload.folder_id,
                sort_order=payload.sort_order,
                location_source="user",
            )
        except (ExplorerInvalidMoveError, ExplorerError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExplorerItemLocationResponseSchema.model_validate(
            {"location": location.as_dict()}
        )

    @app.patch(
        "/api/explorer/items/{item_type}/{item_id}/icon",
        response_model=ExplorerItemIconResponseSchema,
    )
    def update_explorer_item_icon(
        item_type: str,
        item_id: str,
        payload: ExplorerItemIconUpdateSchema,
    ) -> ExplorerItemIconResponseSchema:
        _ensure_explorer_item_exists(item_type, item_id)
        try:
            item_icon = explorer.set_item_icon(
                item_type=item_type,
                item_id=item_id,
                icon=payload.icon,
            )
        except ExplorerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExplorerItemIconResponseSchema.model_validate({"icon": item_icon})

    @app.get("/api/agent-state", response_model=AgentStateResponseSchema)
    def get_agent_state(session_id: str | None = None) -> AgentStateResponseSchema:
        record = sessions.load_record(session_id) if session_id else _latest_session_record(sessions)
        if record is None:
            return AgentStateResponseSchema()
        record = _reconcile_ready_knowledge_items(record)
        return _agent_state_for_record(record, resolved_knowledge_job_repository)

    return app


def _latest_session_record(sessions: FileSessionStore) -> SessionRecord | None:
    records = sessions.list_recent_records()
    return records[0] if records else None


def _agent_state_for_record(
    record: SessionRecord,
    knowledge_job_repository: InMemoryKnowledgeJobRepository | None = None,
) -> AgentStateResponseSchema:
    assistant_messages = [
        message for message in record.messages if message.role == "assistant"
    ]
    latest = assistant_messages[-1] if assistant_messages else None
    queue: list[KnowledgeQueueItemSchema] = []
    recent: list[AgentDecisionSummarySchema] = []
    for message in assistant_messages:
        context = message.assistant_context
        for item in context.state_items:
            queue.append(
                KnowledgeQueueItemSchema(
                    item_id=item.item_id,
                    title=item.title,
                    state=item.state,
                    reason=item.reason,
                    source_session_id=record.session_id,
                    source_message_id=item.source_message_id or message.message_id,
                    node_id=item.node_id,
                    error_message=item.error_message,
                )
            )
        if context.orchestration_plan is not None:
            recent.append(
                AgentDecisionSummarySchema(
                    session_id=record.session_id,
                    message_id=message.message_id,
                    route=context.orchestration_plan.route,
                    intent=context.orchestration_plan.intent,
                    persistence_decision=context.orchestration_plan.persistence_decision,
                    result=context.orchestration_plan.user_visible_summary,
                )
            )
    if knowledge_job_repository is not None:
        for job in knowledge_job_repository.list_jobs(record.session_id):
            draft = job.draft_requests[0] if job.draft_requests else None
            anchor = job.anchors[0] if job.anchors else None
            queue.append(
                KnowledgeQueueItemSchema(
                    item_id=job.job_id,
                    title=(
                        draft.title
                        if draft is not None
                        else anchor.label
                        if anchor is not None
                        else job.question
                    ),
                    draft_type=draft.draft_type if draft is not None else "",
                    state=job.status,
                    reason=draft.reason if draft is not None else "",
                    source_session_id=job.session_id,
                    node_id=anchor.node_id if anchor is not None else None,
                    error_message=job.error_message,
                )
            )
    current_turn = None
    if latest is not None and latest.assistant_context.orchestration_plan is not None:
        plan = latest.assistant_context.orchestration_plan
        current_turn = AgentTurnStateSchema(
            session_id=record.session_id,
            message_id=latest.message_id,
            route=plan.route,
            intent=plan.intent,
            confidence=plan.confidence,
            persistence_decision=plan.persistence_decision,
            user_visible_summary=plan.user_visible_summary,
            detected_scope_ids=list(plan.detected_scope_ids),
            profile_layers_used=list(plan.profile_layers_used),
            profile_context_summary=plan.profile_context_summary,
            active_node_ids=list(record.branch_context.active_node_ids),
            candidate_drafts=[
                KnowledgeDraftCandidateSchema(
                    title=draft.title,
                    draft_type=draft.draft_type,
                    reason=draft.reason,
                )
                for draft in plan.candidate_drafts
            ],
        )
    memory_scope = MemoryScopeStateSchema()
    if current_turn is not None:
        memory_scope = MemoryScopeStateSchema(
            detected_scope_ids=list(current_turn.detected_scope_ids),
            profile_layers_used=list(current_turn.profile_layers_used),
            profile_context_summary=current_turn.profile_context_summary,
            has_global_user_profile="global_user" in current_turn.profile_layers_used,
            has_scope_memory=any(layer.startswith("scope_memory:") for layer in current_turn.profile_layers_used),
        )
    return AgentStateResponseSchema(
        current_turn=current_turn,
        knowledge_queue=queue,
        memory_scope=memory_scope,
        context_health=ContextHealthSchema(
            active_node_count=len(record.branch_context.active_node_ids),
            summary_node_count=len(record.branch_context.summary_node_ids),
            pending_draft_count=sum(
                1 for item in queue if item.state in {"suggested", "queued", "running", "writing"}
            ),
            failed_item_count=sum(1 for item in queue if item.state == "failed"),
            symbol_conflict_count=sum(
                len(message.assistant_context.symbol_conflicts)
                for message in assistant_messages[-3:]
            ),
        ),
        recent_decisions=list(reversed(recent[-10:])),
    )


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-_")
    return slug or "generated-node"


def _generate_session_identity(
    session_id: str | None,
    question: str,
    answer: str,
    provider_profile: ProviderProfile | None,
    credential_registry: FileCredentialRegistry,
    provider_options_payload: dict[str, object],
    provider_gateway: ProviderGateway | object | None,
) -> tuple[str, str]:
    fallback_title = question.strip()
    fallback = (fallback_title, DEFAULT_SESSION_CATEGORY)
    title_profile = _title_generation_provider_profile(
        provider_profile=provider_profile,
        credential_registry=credential_registry,
        provider_options_payload=provider_options_payload,
    )
    if title_profile is None or provider_gateway is None:
        return fallback

    prompt_messages = [
        f"User: {question.strip()}",
        f"Assistant: {answer.strip()}",
    ]
    category_guide = "\n".join(
        f'- "{category}": {description}'
        for category, description in MATH_SESSION_CATEGORIES.items()
    )
    try:
        provider_result = provider_gateway.generate(
            title_profile,
            ProviderRequest(
                system_instruction=(
                    "Create a short title and choose the single best category for this math "
                    "conversation. Trust the mathematical subject, not superficial keywords. "
                    "Prefer the more specific category when a topic fits several categories "
                    "(for example, group theory over algebra, linear algebra over algebra, and "
                    "topology over geometry). Return exactly one JSON object with two string "
                    'fields: {"title":"...","category":"..."}. The title must have no '
                    "punctuation suffix. The category must be one of these ids:\n"
                    f"{category_guide}"
                ),
                user_message="\n".join(prompt_messages),
                session_id=session_id,
                session_id_suffix="utility",
                purpose="session_identity",
            ),
        )
    except (KeyError, ProviderError, AttributeError, TypeError, ValueError):
        return fallback

    parsed = _parse_session_identity(provider_result.output_text)
    return parsed or fallback


def _parse_session_identity(output_text: str) -> tuple[str, str] | None:
    candidate = output_text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        payload = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    title = payload.get("title")
    category = payload.get("category")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(category, str) or category not in MATH_SESSION_CATEGORIES:
        return None
    return title.strip().rstrip("。.!！?？;；:："), category


def _title_generation_provider_profile(
    provider_profile: ProviderProfile | None,
    credential_registry: FileCredentialRegistry,
    provider_options_payload: dict[str, object],
) -> ProviderProfile | None:
    default_options = dict(provider_options_payload.get("default_options") or {})
    utility_config = dict(default_options.get("utility_model") or {})
    provider_type = utility_config.get("provider_type")
    model = utility_config.get("model")
    credential_id = utility_config.get("credential_id")
    if not provider_type or not model:
        return None
    if (
        provider_profile is not None
        and provider_profile.provider_type == provider_type
        and provider_profile.credential_id
        and (
            not credential_id
            or provider_profile.credential_id == str(credential_id)
        )
    ):
        return ProviderProfile(
            provider_type=provider_type,
            model=str(model),
            credential_id=provider_profile.credential_id,
            base_url=provider_profile.base_url,
            options=dict(provider_profile.options),
        )

    for item in _credential_summaries(credential_registry):
        if credential_id and item.get("credential_id") == credential_id:
            return ProviderProfile(
                provider_type=str(item.get("provider_type") or provider_type),
                model=str(model),
                credential_id=str(item["credential_id"]),
                base_url=item.get("base_url"),
            )
    for item in _credential_summaries(credential_registry):
        if item.get("provider_type") == provider_type:
            return ProviderProfile(
                provider_type=provider_type,
                model=str(model),
                credential_id=str(item["credential_id"]),
                base_url=item.get("base_url"),
            )
    return None


def _schema_to_provider_profile(payload: ProviderProfileSchema | None) -> ProviderProfile | None:
    if payload is None:
        return None
    return ProviderProfile(
        provider_type=payload.provider_type,
        model=payload.model,
        credential_id=payload.credential_id,
        base_url=payload.base_url,
        options=payload.options,
    )


def _provider_profile_to_schema(
    provider_profile: ProviderProfile | None,
) -> ProviderProfileSchema | None:
    if provider_profile is None:
        return None
    return ProviderProfileSchema.model_validate(
        {
            "provider_type": provider_profile.provider_type,
            "model": provider_profile.model,
            "credential_id": provider_profile.credential_id,
            "base_url": provider_profile.base_url,
            "options": provider_profile.options,
        }
    )


def _default_model_selection_to_model_selection(
    payload: DefaultModelSelectionSchema | None,
) -> ModelSelection | None:
    if payload is None:
        return None
    return ModelSelection(
        provider_id=str(payload.provider_id) if payload.provider_id else None,
        provider_type=payload.provider_type,
        model=payload.model,
        credential_id=str(payload.credential_id) if payload.credential_id else None,
    )


def _conversation_model_from_default_options(
    provider_options_payload: dict[str, object],
) -> ModelSelection | None:
    default_options = dict(provider_options_payload.get("default_options") or {})
    conversation_config = dict(default_options.get("conversation_model") or {})
    provider_type = conversation_config.get("provider_type")
    model = conversation_config.get("model")
    if not provider_type or not model:
        return None
    return ModelSelection(
        provider_id=(
            str(conversation_config["provider_id"])
            if conversation_config.get("provider_id")
            else None
        ),
        provider_type=str(provider_type),
        model=str(model),
        credential_id=(
            str(conversation_config["credential_id"])
            if conversation_config.get("credential_id")
            else None
        ),
    )


def _resolved_conversation_model_selection(
    *,
    payload: AskRequestSchema,
    existing_record: SessionRecord | None,
    provider_options_payload: dict[str, object],
    provider_profile: ProviderProfile | None,
) -> ModelSelection | None:
    if payload.conversation_model is not None:
        return _default_model_selection_to_model_selection(payload.conversation_model)
    if existing_record is not None and existing_record.conversation_model is not None:
        return existing_record.conversation_model
    if provider_profile is not None:
        # Legacy compatibility: a client may still send provider_profile; persist a minimal selection.
        return ModelSelection(
            provider_id=None,
            provider_type=provider_profile.provider_type,
            model=provider_profile.model,
            credential_id=provider_profile.credential_id,
        )
    return _conversation_model_from_default_options(provider_options_payload)


def _resolve_provider_profile_from_selection(
    *,
    selection: ModelSelection | None,
    credential_registry: FileCredentialRegistry,
    provider_options_payload: dict[str, object],
) -> ProviderProfile | None:
    if selection is None:
        return None
    provider_type = selection.provider_type
    model = selection.model
    credential_id = selection.credential_id

    candidates = _credential_summaries(credential_registry)
    picked: dict[str, object] | None = None
    if credential_id:
        picked = next(
            (item for item in candidates if item.get("credential_id") == credential_id),
            None,
        )
        if picked is None:
            return None
    if picked is None and selection.provider_id:
        picked = next(
            (item for item in candidates if item.get("provider_id") == selection.provider_id),
            None,
        )
    if picked is None:
        picked = next(
            (item for item in candidates if item.get("provider_type") == provider_type),
            None,
        )
    if picked is None:
        return None

    # Prefer the credential base_url when present, otherwise fall back to catalog default_base_url.
    base_url = picked.get("base_url")
    if not base_url and selection.provider_id:
        catalog = list(provider_options_payload.get("provider_catalog") or [])
        for item in catalog:
            if isinstance(item, dict) and item.get("provider_id") == selection.provider_id:
                base_url = item.get("default_base_url")
                break
    return ProviderProfile(
        provider_type=str(picked.get("provider_type") or provider_type),
        model=str(model),
        credential_id=str(picked["credential_id"]),
        base_url=str(base_url) if base_url else None,
        options={},
    )


def _resolved_conversation_provider_profile(
    *,
    payload: AskRequestSchema,
    existing_record: SessionRecord | None,
    credential_registry: FileCredentialRegistry,
    provider_options_payload: dict[str, object],
) -> ProviderProfile | None:
    # Highest precedence: explicit provider_profile payload (legacy / system override).
    if payload.provider_profile is not None:
        return _schema_to_provider_profile(payload.provider_profile)

    # Next: explicit conversation_model selection in the request.
    selection = _resolved_conversation_model_selection(
        payload=payload,
        existing_record=existing_record,
        provider_options_payload=provider_options_payload,
        provider_profile=(existing_record.provider_profile if existing_record else None),
    )
    resolved = _resolve_provider_profile_from_selection(
        selection=selection,
        credential_registry=credential_registry,
        provider_options_payload=provider_options_payload,
    )
    if resolved is not None:
        return resolved
    # Fallback to any stored provider_profile (older sessions).
    return existing_record.provider_profile if existing_record is not None else None


def _hydrated_record_provider_profile(
    record: SessionRecord,
    *,
    credential_registry: FileCredentialRegistry,
    provider_options_payload: dict[str, object],
) -> SessionRecord:
    if record.provider_profile is not None or record.conversation_model is None:
        return record
    resolved = _resolve_provider_profile_from_selection(
        selection=record.conversation_model,
        credential_registry=credential_registry,
        provider_options_payload=provider_options_payload,
    )
    if resolved is None:
        return record
    return replace(record, provider_profile=resolved)


def _record_to_session_schema(record: SessionRecord) -> SessionSchema:
    return SessionSchema(
        session_id=record.session_id,
        title=record.title,
        icon=record.icon,
        conversation_model=_model_selection_to_schema(record.conversation_model),
        provider_profile=_provider_profile_to_schema(record.provider_profile),
        default_answer_style_id=record.default_answer_style_id,
        strategy_agent_id=record.strategy_agent_id,
        knowledge_approval_policy=record.knowledge_approval_policy,
        knowledge_scope_id=record.branch_context.knowledge_scope_id,
        branch=_branch_context_to_schema(record.branch_context),
        messages=[_session_message_to_schema(message) for message in record.messages],
    )


def _model_selection_to_schema(
    selection: ModelSelection | None,
) -> DefaultModelSelectionSchema | None:
    if selection is None:
        return None
    return DefaultModelSelectionSchema.model_validate(
        {
            "provider_id": selection.provider_id,
            "provider_type": selection.provider_type,
            "credential_id": selection.credential_id,
            "model": selection.model,
        }
    )


def _branch_context_to_schema(
    branch_context: SessionBranchContext,
) -> SessionBranchSchema:
    return SessionBranchSchema(
        branch_id=branch_context.branch_id,
        parent_session_id=branch_context.parent_session_id,
        root_session_id=branch_context.root_session_id,
        focus_question=branch_context.focus_question,
        fork_anchor=(
            SessionForkAnchorSchema(
                type=branch_context.fork_anchor.type,
                message_id=branch_context.fork_anchor.message_id,
                node_id=branch_context.fork_anchor.node_id,
                source_message_id=branch_context.fork_anchor.source_message_id,
            )
            if branch_context.fork_anchor is not None
            else None
        ),
        active_node_ids=list(branch_context.active_node_ids),
        summary_node_ids=list(branch_context.summary_node_ids),
        active_symbols=dict(branch_context.active_symbols),
    )


def _meaningful_branch_context(
    branch_context: SessionBranchContext | None,
) -> SessionBranchContext | None:
    if branch_context is None:
        return None
    if any(
        [
            branch_context.branch_id,
            branch_context.parent_session_id,
            branch_context.root_session_id,
            branch_context.fork_anchor is not None,
            branch_context.focus_question,
            branch_context.active_node_ids,
            branch_context.summary_node_ids,
            branch_context.active_symbols,
            branch_context.knowledge_scope_id,
        ]
    ):
        return branch_context
    return None


def _session_message_to_schema(message: SessionMessage) -> SessionMessageSchema:
    return SessionMessageSchema(
        message_id=message.message_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        provider_name=message.provider_name,
        raw_response_meta=message.raw_response_meta,
        assistant_context=SessionAssistantContextSchema(
            action_type=message.assistant_context.action_type,
            referenced_node_ids=message.assistant_context.referenced_node_ids,
            anchors=[
                _answer_anchor_to_schema(anchor).model_dump()
                for anchor in message.assistant_context.anchors
            ],
            symbol_conflicts=message.assistant_context.symbol_conflicts,
            alignment_notes=message.assistant_context.alignment_notes,
            compact_summary=message.assistant_context.compact_summary,
            orchestration_plan=(
                _orchestration_plan_to_schema(message.assistant_context.orchestration_plan)
                if message.assistant_context.orchestration_plan is not None
                else None
            ),
            state_items=[
                _agent_state_item_to_schema(item).model_dump()
                for item in message.assistant_context.state_items
            ],
        ),
    )


def _orchestration_plan_to_schema(plan: OrchestrationPlan) -> OrchestrationPlanSchema:
    return OrchestrationPlanSchema(
        route=plan.route,
        intent=plan.intent,
        persistence_decision=plan.persistence_decision,
        confidence=plan.confidence,
        user_visible_summary=plan.user_visible_summary,
        detected_scope_ids=list(plan.detected_scope_ids),
        profile_layers_used=list(plan.profile_layers_used),
        profile_context_summary=plan.profile_context_summary,
        candidate_drafts=[
            KnowledgeDraftCandidateSchema(
                title=draft.title,
                draft_type=draft.draft_type,
                reason=draft.reason,
            )
            for draft in plan.candidate_drafts
        ],
        strategy_mode=plan.strategy_mode,
        strategy_reason=plan.strategy_reason,
        knowledge_scope_id=plan.knowledge_scope_id,
        knowledge_scope_label=plan.knowledge_scope_label,
        authorization=KnowledgeAuthorizationDecisionSchema(
            policy=plan.authorization.policy,
            mode=plan.authorization.mode,
            status=plan.authorization.status,
            risk_level=plan.authorization.risk_level,
            operation=plan.authorization.operation,
            reason=plan.authorization.reason,
        ),
    )


def _agent_state_item_to_schema(item: AgentStateItem) -> AgentStateItemSchema:
    return AgentStateItemSchema(
        item_id=item.item_id,
        kind=item.kind,
        state=item.state,
        title=item.title,
        reason=item.reason,
        source_message_id=item.source_message_id,
        node_id=item.node_id,
        error_message=item.error_message,
    )


def _answer_anchor_to_schema(anchor: AnswerAnchor) -> AnswerAnchorSchema:
    return AnswerAnchorSchema(
        anchor_id=anchor.anchor_id,
        label=anchor.label,
        status=anchor.status,
        node_id=anchor.node_id,
    )


def _compact_session_record(
    repository: MarkdownKnowledgeRepository,
    record: SessionRecord,
    payload: CompactRequestSchema,
) -> SessionRecord:
    active_node_ids = list(record.branch_context.active_node_ids)
    summary_node_ids = list(record.branch_context.summary_node_ids)
    recent_referenced_node_ids = _latest_assistant_referenced_node_ids(record.messages)
    merged_summary_node_ids = _merge_unique_ids(
        summary_node_ids,
        [
            node_id
            for node_id in recent_referenced_node_ids
            if node_id not in active_node_ids and node_id not in summary_node_ids
        ],
    )
    compact_reference_node_ids = _merge_unique_ids(
        active_node_ids,
        merged_summary_node_ids,
        recent_referenced_node_ids,
    )
    compact_scope_nodes = _load_nodes_by_ids(
        repository,
        _merge_unique_ids(active_node_ids, merged_summary_node_ids),
    )
    merged_groups = _compact_merged_groups(
        [node for node in compact_scope_nodes if node.id in merged_summary_node_ids]
    )
    symbol_conflicts = SymbolRegistry().build_context(compact_scope_nodes).conflicts
    note_text = payload.note or record.branch_context.focus_question or "current branch"
    compact_message = SessionMessage(
        role="assistant",
        content=(
            f"Compacted branch: {note_text}. "
            f"Active nodes: {', '.join(active_node_ids) or 'none'}. "
            f"Summary nodes: {', '.join(merged_summary_node_ids) or 'none'}."
        ),
        assistant_context=SessionAssistantContext(
            action_type="compact",
            referenced_node_ids=compact_reference_node_ids,
            symbol_conflicts=symbol_conflicts,
            alignment_notes=_compact_alignment_notes(record.branch_context.active_symbols),
            compact_summary=_compact_summary(
                record.branch_context,
                merged_summary_node_ids,
                merged_groups,
            ),
        ),
    )
    return SessionRecord(
        session_id=record.session_id,
        title=record.title,
        icon=record.icon,
        conversation_model=record.conversation_model,
        provider_profile=record.provider_profile,
        default_answer_style_id=record.default_answer_style_id,
        strategy_agent_id=record.strategy_agent_id,
        knowledge_approval_policy=record.knowledge_approval_policy,
        branch_context=SessionBranchContext(
            branch_id=record.branch_context.branch_id,
            parent_session_id=record.branch_context.parent_session_id,
            root_session_id=record.branch_context.root_session_id,
            focus_question=record.branch_context.focus_question,
            fork_anchor=record.branch_context.fork_anchor,
            active_node_ids=active_node_ids,
            summary_node_ids=merged_summary_node_ids,
            active_symbols=dict(record.branch_context.active_symbols),
            knowledge_scope_id=record.branch_context.knowledge_scope_id,
        ),
        messages=[*record.messages, compact_message],
    )


def _compact_alignment_notes(active_symbols: dict[str, str]) -> list[str]:
    if not active_symbols:
        return ["No active symbols to align."]
    return [
        "Aligned active symbols: "
        + ", ".join(f"{symbol}={meaning}" for symbol, meaning in sorted(active_symbols.items()))
        + "."
    ]


def _compact_summary(
    branch_context: SessionBranchContext,
    summary_node_ids: list[str],
    merged_groups: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "focus_question": branch_context.focus_question,
        "active_node_ids": list(branch_context.active_node_ids),
        "summary_node_ids": list(summary_node_ids),
        "symbol_snapshot": dict(branch_context.active_symbols),
        "merged_groups": list(merged_groups or []),
    }


def _compact_merged_groups(nodes: list[KnowledgeNode]) -> list[dict[str, object]]:
    merged_groups: list[dict[str, object]] = []
    assigned_node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        if node.id in assigned_node_ids:
            continue
        group_node_ids = [node.id]
        for candidate in nodes[index + 1 :]:
            if candidate.id in assigned_node_ids:
                continue
            if candidate.parent_id != node.parent_id or candidate.parent_id is None:
                continue
            if not _summary_terms_overlap(node.summary, candidate.summary):
                continue
            group_node_ids.append(candidate.id)
            assigned_node_ids.add(candidate.id)
        if len(group_node_ids) > 1:
            assigned_node_ids.add(node.id)
            merged_groups.append(
                {
                    "canonical_node_id": node.id,
                    "merged_node_ids": group_node_ids,
                    "reason": (
                        f"Shared {node.parent_id} parent and overlapping summary terms."
                    ),
                }
            )
    return merged_groups


def _summary_terms_overlap(left_summary: str, right_summary: str) -> bool:
    return bool(_summary_terms(left_summary) & _summary_terms(right_summary))


def _summary_terms(summary: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", summary.lower())
        if len(token) > 3 and token not in _SUMMARY_STOPWORDS
    }


_SUMMARY_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "between",
    "both",
    "closed",
    "each",
    "from",
    "into",
    "linearly",
    "more",
    "over",
    "same",
    "scalar",
    "space",
    "that",
    "their",
    "this",
    "under",
    "with",
}


def _load_nodes_by_ids(
    repository: MarkdownKnowledgeRepository,
    node_ids: list[str],
) -> list[KnowledgeNode]:
    loaded_nodes: list[KnowledgeNode] = []
    seen_node_ids: set[str] = set()
    for node_id in node_ids:
        if node_id in seen_node_ids:
            continue
        seen_node_ids.add(node_id)
        loaded_nodes.append(repository.get_node(node_id))
    return loaded_nodes


def _display_reference_payload(
    repository: MarkdownKnowledgeRepository,
    reference: NodeReference,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "node_id": reference.node_id,
        "title": None,
        "summary": None,
        "reason": reference.reason,
        "type": None,
        "status": None,
    }
    try:
        target = repository.get_node(reference.node_id)
    except FileNotFoundError:
        return payload
    payload.update(
        {
            "title": target.title,
            "summary": target.summary,
            "type": target.type,
            "status": target.status,
        }
    )
    return payload


def _related_discussion_payload(
    session_store: FileSessionStore,
    session_id: str,
) -> dict[str, object]:
    record = session_store.load_record(session_id)
    if record is None:
        return {
            "session_id": session_id,
            "title": session_id,
            "preview": None,
            "message_count": None,
            "focus_question": None,
        }

    focus_question = record.branch_context.focus_question
    return {
        "session_id": session_id,
        "title": record.title or focus_question or session_id,
        "preview": _discussion_preview(record.messages),
        "message_count": record.message_count,
        "focus_question": focus_question,
    }


def _discussion_preview(messages: list[SessionMessage]) -> str | None:
    for message in reversed(messages):
        normalized = re.sub(r"\s+", " ", message.content).strip()
        if not normalized:
            continue
        if len(normalized) <= 100:
            return normalized
        return f"{normalized[:97]}..."
    return None


def _latest_assistant_referenced_node_ids(messages: list[SessionMessage]) -> list[str]:
    for message in reversed(messages):
        if message.role != "assistant":
            continue
        if message.assistant_context.referenced_node_ids:
            return list(message.assistant_context.referenced_node_ids)
    return []


def _merge_unique_ids(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen_node_ids: set[str] = set()
    for group in groups:
        for node_id in group:
            if node_id in seen_node_ids:
                continue
            seen_node_ids.add(node_id)
            merged.append(node_id)
    return merged


def _session_tree_metadata(
    records: list[SessionRecord],
) -> dict[str, dict[str, object]]:
    record_by_id = {record.session_id: record for record in records}
    children_by_parent: dict[str, list[str]] = {}
    for record in records:
        parent_session_id = record.branch_context.parent_session_id
        if parent_session_id is None:
            continue
        children_by_parent.setdefault(parent_session_id, []).append(record.session_id)

    depth_cache: dict[str, int] = {}

    def branch_depth(session_id: str, ancestry: tuple[str, ...] = ()) -> int:
        if session_id in depth_cache:
            return depth_cache[session_id]
        record = record_by_id.get(session_id)
        if record is None:
            depth_cache[session_id] = 0
            return 0
        parent_session_id = record.branch_context.parent_session_id
        if parent_session_id is None or parent_session_id not in record_by_id:
            depth_cache[session_id] = 0
            return 0
        if parent_session_id in ancestry:
            depth_cache[session_id] = 0
            return 0
        depth = branch_depth(parent_session_id, ancestry + (session_id,)) + 1
        depth_cache[session_id] = depth
        return depth

    return {
        record.session_id: {
            "branch_depth": branch_depth(record.session_id),
            "child_session_ids": list(
                children_by_parent.get(record.session_id, [])
            ),
        }
        for record in records
    }


def _fork_branch_context(
    repository: MarkdownKnowledgeRepository,
    parent_record: SessionRecord,
    payload: SessionForkRequestSchema,
) -> SessionBranchContext:
    root_session_id = (
        parent_record.branch_context.root_session_id or parent_record.session_id
    )
    active_node_ids: list[str] = []
    summary_node_ids: list[str] = []

    fork_anchor = payload.fork_anchor
    if fork_anchor.type == "node":
        if fork_anchor.node_id is None:
            raise HTTPException(status_code=400, detail="Node fork anchor requires node_id")
        anchor_node = _load_anchor_node(repository, fork_anchor.node_id)
        active_node_ids = [anchor_node.id]
        summary_node_ids = _related_summary_node_ids(repository, anchor_node)
        fork_anchor = SessionForkAnchor(
            type="node",
            node_id=anchor_node.id,
            source_message_id=(
                fork_anchor.source_message_id
                or parent_record.last_committed_message_id
            ),
        )
    elif fork_anchor.type == "message":
        if fork_anchor.message_id is None:
            raise HTTPException(status_code=400, detail="Message fork anchor requires message_id")
        active_node_ids = _message_anchor_node_ids(parent_record, fork_anchor.message_id)
        summary_node_ids = _summary_node_ids_for_anchors(repository, active_node_ids)
    active_symbols = _branch_symbol_constraints(
        repository,
        active_node_ids=active_node_ids,
    )

    return SessionBranchContext(
        branch_id=f"branch-{uuid4().hex[:8]}",
        parent_session_id=parent_record.session_id,
        root_session_id=root_session_id,
        fork_anchor=fork_anchor,
        focus_question=payload.focus_question,
        active_node_ids=active_node_ids,
        summary_node_ids=summary_node_ids,
        active_symbols=active_symbols,
        knowledge_scope_id=parent_record.branch_context.knowledge_scope_id,
    )


def _message_anchor_node_ids(
    parent_record: SessionRecord,
    message_id: str,
) -> list[str]:
    anchor_message = next(
        (message for message in parent_record.messages if message.message_id == message_id),
        None,
    )
    if anchor_message is None:
        raise HTTPException(status_code=404, detail="Fork anchor message not found")
    if anchor_message.role != "assistant":
        raise HTTPException(
            status_code=404,
            detail="Fork anchor message must be an assistant message with references",
        )
    referenced_node_ids = anchor_message.assistant_context.referenced_node_ids
    if not referenced_node_ids:
        raise HTTPException(
            status_code=404,
            detail="Fork anchor message must be an assistant message with references",
        )
    seen_node_ids: set[str] = set()
    ordered_node_ids: list[str] = []
    for node_id in referenced_node_ids:
        if node_id in seen_node_ids:
            continue
        seen_node_ids.add(node_id)
        ordered_node_ids.append(node_id)
    return ordered_node_ids


def _summary_node_ids_for_anchors(
    repository: MarkdownKnowledgeRepository,
    anchor_node_ids: list[str],
) -> list[str]:
    summary_node_ids: list[str] = []
    seen_node_ids: set[str] = set(anchor_node_ids)
    for node_id in anchor_node_ids:
        anchor_node = _load_anchor_node(repository, node_id)
        for related_node_id in _related_summary_node_ids(repository, anchor_node):
            if related_node_id in seen_node_ids:
                continue
            seen_node_ids.add(related_node_id)
            summary_node_ids.append(related_node_id)
    return summary_node_ids


def _branch_symbol_constraints(
    repository: MarkdownKnowledgeRepository,
    active_node_ids: list[str],
) -> dict[str, str]:
    selected_nodes: list[KnowledgeNode] = []
    for node_id in active_node_ids:
        selected_nodes.append(_load_anchor_node(repository, node_id))
    return SymbolRegistry().build_context(selected_nodes).symbols


def _load_anchor_node(
    repository: MarkdownKnowledgeRepository,
    node_id: str,
) -> KnowledgeNode:
    try:
        return repository.get_node(node_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fork anchor node not found") from exc


def _related_summary_node_ids(
    repository: MarkdownKnowledgeRepository,
    anchor_node: KnowledgeNode,
) -> list[str]:
    known_node_ids = {node.id for node in repository.list_nodes()}
    related_node_ids: list[str] = []
    seen_node_ids: set[str] = set()

    for candidate_id in [ref.node_id for ref in anchor_node.references]:
        if candidate_id == anchor_node.id or candidate_id not in known_node_ids:
            continue
        if candidate_id in seen_node_ids:
            continue
        seen_node_ids.add(candidate_id)
        related_node_ids.append(candidate_id)

    for reference in repository.list_incoming_references(anchor_node.id):
        candidate_id = reference.node_id
        if candidate_id == anchor_node.id or candidate_id not in known_node_ids:
            continue
        if candidate_id in seen_node_ids:
            continue
        seen_node_ids.add(candidate_id)
        related_node_ids.append(candidate_id)

    return related_node_ids


def _credential_summaries(
    credential_registry: FileCredentialRegistry,
) -> list[dict[str, object]]:
    path = credential_registry.path
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    summaries: list[dict[str, object]] = []
    for item in payload.get("credentials", []):
        summary: dict[str, object] = {
            "credential_id": item["credential_id"],
            "provider_type": item.get("provider_type"),
            "has_headers": bool(item.get("headers")),
        }
        if item.get("provider_id") is not None:
            summary["provider_id"] = item.get("provider_id")
        if item.get("default_model") is not None:
            summary["default_model"] = item.get("default_model")
        if item.get("base_url") is not None:
            summary["base_url"] = item.get("base_url")
        if item.get("models") is not None:
            summary["models"] = item.get("models")
        summaries.append(summary)
    return summaries


def _credential_api_key(credential_registry: FileCredentialRegistry, credential_id: str) -> str:
    try:
        return credential_registry.get(credential_id).api_key
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown credential_id: {credential_id}",
        ) from exc


def _selection_draft_title_seed(selected_text: str, prompt_kind: str) -> str:
    lines = selected_text.splitlines()
    candidate = next((line.strip() for line in lines if line.strip()), "")
    if not candidate and lines:
        candidate = lines[0].strip()
    candidate = re.sub(r"^[\s\W_]+|[\s\W_]+$", "", candidate, flags=re.UNICODE)
    candidate = candidate[:48].rstrip()
    label_by_prompt_kind = {
        "definition": "Definition",
        "intuition_node": "Intuition",
        "example": "Application Example",
        "proof": "Proof",
    }
    label = label_by_prompt_kind.get(prompt_kind, "Knowledge")
    if candidate:
        return f"{candidate} {label}"
    return label


def _upsert_credential(
    credential_registry: FileCredentialRegistry, payload: CredentialWriteSchema
) -> dict[str, object]:
    path = credential_registry.path
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_payload = {"credentials": []}
    if path.exists():
        existing_payload = json.loads(path.read_text(encoding="utf-8"))
    credential_id = str(payload.provider_id or payload.credential_id)
    credentials = [
        item
        for item in existing_payload.get("credentials", [])
        if item.get("credential_id") != payload.credential_id
        and item.get("credential_id") != credential_id
        and (
            payload.provider_id is None
            or item.get("provider_id") != payload.provider_id
        )
    ]
    credentials.append(
        {
            "credential_id": credential_id,
            "api_key": payload.api_key,
            "provider_type": payload.provider_type,
            "provider_id": payload.provider_id,
            "headers": payload.headers,
            "base_url": payload.base_url,
            "default_model": payload.default_model,
            "models": payload.models,
        }
    )
    path.write_text(
        json.dumps({"credentials": credentials}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    response: dict[str, object] = {
        "credential_id": credential_id,
        "provider_type": payload.provider_type,
        "has_headers": bool(payload.headers),
    }
    if payload.provider_id is not None:
        response["provider_id"] = payload.provider_id
    if payload.default_model is not None:
        response["default_model"] = payload.default_model
    if payload.base_url is not None:
        response["base_url"] = payload.base_url
    if payload.models:
        response["models"] = payload.models
    return response


def _sse_event(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
