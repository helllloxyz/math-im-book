import logging
from pathlib import Path
from threading import Barrier

from math_im_book.domain.models import (
    AnswerAnchor,
    PendingDraftRequest,
    ProviderProfile,
    ProviderResult,
)
from math_im_book.services.knowledge_jobs import InMemoryKnowledgeJobRepository
from math_im_book.storage.explorer import ExplorerStore
from math_im_book.storage.markdown import MarkdownKnowledgeRepository


def test_knowledge_job_logs_lifecycle_without_content(tmp_path: Path, caplog) -> None:
    class Gateway:
        def generate(
            self,
            profile: ProviderProfile,
            request: object,
        ) -> ProviderResult:
            return ProviderResult(
                output_text='{"summary":"A summary.","detail":"A detail."}',
                provider_name="test",
            )

    jobs = InMemoryKnowledgeJobRepository(
        MarkdownKnowledgeRepository(tmp_path),
        provider_gateway=Gateway(),
        auto_start=False,
    )
    with caplog.at_level(
        logging.INFO,
        logger="uvicorn.error.math_im_book.knowledge_jobs",
    ):
        job = jobs.submit_compile_job(
            session_id="chat-1",
            question="private question content",
            anchors=[],
            selected_node_ids=[],
            draft_requests=[
                PendingDraftRequest(
                    title="Private draft title",
                    draft_type="summary",
                    reason="Private draft reason",
                )
            ],
            provider_profile=ProviderProfile(
                provider_type="openai_compatible",
                model="test-model",
                credential_id="test",
            ),
        )
        jobs.run_job(job.job_id)

    log_output = "\n".join(record.getMessage() for record in caplog.records)
    assert "Knowledge job queued" in log_output
    assert "Knowledge job started" in log_output
    assert "Knowledge job completed" in log_output
    assert f"job={job.job_id}" in log_output
    assert "session=chat-1" in log_output
    assert "private question content" not in log_output
    assert "Private draft title" not in log_output
    assert "Private draft reason" not in log_output


def test_compile_job_without_provider_fails_without_writing_fallback_node(
    tmp_path: Path,
) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(repository, auto_start=False)
    job = jobs.submit_compile_job(
        question="线性代数",
        anchors=[
            AnswerAnchor(
                anchor_id="what-is-linear-algebra",
                label="What is Linear Algebra?",
                status="pending",
            )
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="What is Linear Algebra?",
                draft_type="missing_definition",
                reason="Introduce the topic.",
            )
        ],
    )

    failed = jobs.run_job(job.job_id)

    assert failed.status == "failed"
    assert "requires a provider profile and provider gateway" in failed.error_message
    try:
        repository.get_node("what-is-linear-algebra")
    except FileNotFoundError:
        pass
    else:  # pragma: no cover - assertion branch
        raise AssertionError("missing provider must not write fallback node")


def test_failed_compile_job_preserves_error_message(tmp_path: Path) -> None:
    class FailingGateway:
        def generate(self, profile: ProviderProfile, request: object, **kwargs: object) -> object:
            raise RuntimeError("provider unavailable")

    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=FailingGateway(),
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="linear algebra",
        anchors=[
            AnswerAnchor(
                anchor_id="linear-algebra",
                label="Linear Algebra",
                status="pending",
            )
        ],
        selected_node_ids=[],
        draft_requests=[],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    failed_job = jobs.run_job(job.job_id)

    assert failed_job.status == "failed"
    assert failed_job.error_message == "provider unavailable"


def test_compile_job_sends_symbol_constraints_and_saves_them(tmp_path: Path) -> None:
    class RecordingGateway:
        def __init__(self) -> None:
            self.request = None

        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            self.request = request
            return ProviderResult(
                output_text='{"summary":"A reusable note.","detail":"A reusable detail."}',
                provider_name="test",
            )

    gateway = RecordingGateway()
    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=gateway,
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="linear algebra",
        anchors=[
            AnswerAnchor(
                anchor_id="linear-algebra",
                label="Linear Algebra",
                status="pending",
            )
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Linear Algebra",
                draft_type="missing_definition",
                reason="Introduce the topic.",
            )
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
        symbol_constraints={"V": "the active vector space", "T": "a linear operator"},
        symbol_conflicts=["Symbol T has competing local meanings."],
    )

    jobs.run_job(job.job_id)

    assert gateway.request is not None
    assert "Symbol constraints:" in gateway.request.user_message
    assert "- T: a linear operator" in gateway.request.user_message
    assert "- V: the active vector space" in gateway.request.user_message
    assert "Symbol conflicts:" in gateway.request.user_message
    assert "- Symbol T has competing local meanings." in gateway.request.user_message
    node = repository.get_node("linear-algebra")
    assert node.symbols == {
        "T": "a linear operator",
        "V": "the active vector space",
    }


def test_compile_job_uses_draft_type_and_prompt_metadata(tmp_path: Path) -> None:
    class RecordingGateway:
        def __init__(self) -> None:
            self.request = None

        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            self.request = request
            return ProviderResult(
                output_text='{"summary":"A proof summary.","detail":"A proof detail."}',
                provider_name="test",
            )

    gateway = RecordingGateway()
    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=gateway,
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="linear algebra",
        selection_source_text="Proof sketch",
        anchors=[
            AnswerAnchor(
                anchor_id="linear-map",
                label="Linear Map",
                status="pending",
            )
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Linear Map",
                draft_type="proof",
                reason="Turn the sketch into a proof.",
            )
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    completed = jobs.run_job(job.job_id)

    assert gateway.request is not None
    assert "Draft type: proof" in gateway.request.user_message
    assert "Draft reason: Turn the sketch into a proof." in gateway.request.user_message
    assert "Selected text: Proof sketch" in gateway.request.user_message
    assert repository.get_node("linear-map").type == "proof"
    assert completed.anchors[0].status == "ready"


def test_compile_job_requires_user_language_and_delimited_latex(tmp_path: Path) -> None:
    class RecordingGateway:
        def __init__(self) -> None:
            self.request = None

        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            self.request = request
            return ProviderResult(
                output_text=(
                    '{"summary":"余切空间是切空间的对偶空间。",'
                    '"detail":"余切空间记作 $T_p^*M$。"}'
                ),
                provider_name="test",
            )

    gateway = RecordingGateway()
    jobs = InMemoryKnowledgeJobRepository(
        MarkdownKnowledgeRepository(tmp_path),
        provider_gateway=gateway,
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="什么是余切空间？",
        anchors=[],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="余切空间",
                draft_type="definition",
                reason="整理成可复用定义。",
            )
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    completed = jobs.run_job(job.job_id)

    assert completed.status == "completed"
    assert gateway.request is not None
    assert "primary language of the user's Question and Selected text" in (
        gateway.request.system_instruction
    )
    assert "when that language is Chinese" in gateway.request.system_instruction
    assert "use $...$ inline and $$...$$ for display math" in (
        gateway.request.system_instruction
    )
    assert "$T_pM$ rather than T_pM" in gateway.request.system_instruction


def test_compile_job_without_draft_requests_defaults_to_summary_type(
    tmp_path: Path,
) -> None:
    class RecordingGateway:
        def __init__(self) -> None:
            self.request = None

        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            self.request = request
            return ProviderResult(
                output_text='{"summary":"A summary.","detail":"A detail."}',
                provider_name="test",
            )

    gateway = RecordingGateway()
    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=gateway,
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="linear algebra",
        anchors=[],
        selected_node_ids=[],
        draft_requests=[],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    completed = jobs.run_job(job.job_id)

    assert gateway.request is not None
    assert "Draft type: summary" in gateway.request.user_message
    assert repository.get_node("linear-algebra").type == "summary"
    assert completed.anchors[0].label == "linear algebra"


def test_compile_job_accepts_fenced_provider_json(tmp_path: Path) -> None:
    class FencedGateway:
        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            return ProviderResult(
                output_text=(
                    "```json\n"
                    '{"summary":"A real compiled summary.","detail":"A real compiled detail."}\n'
                    "```"
                ),
                provider_name="test",
            )

    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=FencedGateway(),
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="linear algebra",
        anchors=[
            AnswerAnchor(
                anchor_id="linear-algebra",
                label="Linear Algebra",
                status="pending",
            )
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Linear Algebra",
                draft_type="missing_definition",
                reason="Introduce the topic.",
            )
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    completed = jobs.run_job(job.job_id)

    node = repository.get_node("linear-algebra")
    assert completed.status == "completed"
    assert node.summary == "A real compiled summary."
    assert node.detail == "A real compiled detail."


def test_compile_job_records_source_session_on_compiled_node(tmp_path: Path) -> None:
    class Gateway:
        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            return ProviderResult(
                output_text='{"summary":"A reusable note.","detail":"A reusable detail."}',
                provider_name="test",
            )

    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=Gateway(),
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        session_id="session-123",
        question="linear algebra",
        anchors=[
            AnswerAnchor(
                anchor_id="linear-algebra",
                label="Linear Algebra",
                status="pending",
            )
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Linear Algebra",
                draft_type="missing_definition",
                reason="Introduce the topic.",
            )
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    jobs.run_job(job.job_id)

    assert repository.get_node("linear-algebra").source == "session-123"


def test_compile_job_fails_on_invalid_provider_output_without_fallback(
    tmp_path: Path,
) -> None:
    class InvalidGateway:
        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            return ProviderResult(output_text="not json", provider_name="test")

    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=InvalidGateway(),
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="linear algebra",
        anchors=[
            AnswerAnchor(
                anchor_id="linear-algebra",
                label="Linear Algebra",
                status="pending",
            )
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Linear Algebra",
                draft_type="missing_definition",
                reason="Introduce the topic.",
            )
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    failed = jobs.run_job(job.job_id)

    assert failed.status == "failed"
    assert "valid JSON object with non-empty summary and detail" in failed.error_message
    assert failed.anchors[0].status == "failed"
    try:
        repository.get_node("linear-algebra")
    except FileNotFoundError:
        pass
    else:  # pragma: no cover - assertion branch
        raise AssertionError("invalid provider output must not write fallback node")


def test_compile_job_writes_each_draft_request_as_a_node(tmp_path: Path) -> None:
    class MultiGateway:
        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            if "Title: Linear Map" in request.user_message:
                return ProviderResult(
                    output_text='{"summary":"Linear map summary.","detail":"Linear map detail."}',
                    provider_name="test",
                )
            return ProviderResult(
                output_text='{"summary":"Kernel summary.","detail":"Kernel detail."}',
                provider_name="test",
            )

    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=MultiGateway(),
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="linear algebra",
        anchors=[
            AnswerAnchor(anchor_id="linear-map", label="Linear Map", status="pending"),
            AnswerAnchor(anchor_id="kernel", label="Kernel", status="pending"),
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Linear Map",
                draft_type="missing_definition",
                reason="Need a definition.",
            ),
            PendingDraftRequest(
                title="Kernel",
                draft_type="missing_definition",
                reason="Need a definition.",
            ),
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    completed = jobs.run_job(job.job_id)

    assert completed.status == "completed"
    assert [anchor.node_id for anchor in completed.anchors] == ["linear-map", "kernel"]
    assert repository.get_node("linear-map").summary == "Linear map summary."
    assert repository.get_node("kernel").summary == "Kernel summary."


def test_compile_job_compiles_drafts_concurrently_and_preserves_order(
    tmp_path: Path,
) -> None:
    class ConcurrentGateway:
        def __init__(self) -> None:
            self.barrier = Barrier(2, timeout=1)

        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            title_line = request.user_message.splitlines()[0]
            title = title_line.removeprefix("Title: ")
            self.barrier.wait()
            return ProviderResult(
                output_text=(
                    '{"summary":"'
                    + title
                    + ' summary.","detail":"'
                    + title
                    + ' detail."}'
                ),
                provider_name="test",
            )

    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=ConcurrentGateway(),
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="linear algebra",
        anchors=[
            AnswerAnchor(anchor_id="linear-map", label="Linear Map", status="pending"),
            AnswerAnchor(anchor_id="kernel", label="Kernel", status="pending"),
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Linear Map",
                draft_type="missing_definition",
                reason="Need a definition.",
            ),
            PendingDraftRequest(
                title="Kernel",
                draft_type="missing_definition",
                reason="Need a definition.",
            ),
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    completed = jobs.run_job(job.job_id)

    assert completed.status == "completed"
    assert [anchor.node_id for anchor in completed.anchors] == ["linear-map", "kernel"]
    assert repository.get_node("linear-map").summary == "Linear Map summary."
    assert repository.get_node("kernel").summary == "Kernel summary."


def test_compile_job_preserves_distinct_non_ascii_draft_ids(tmp_path: Path) -> None:
    class ChineseGateway:
        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            title_line = request.user_message.splitlines()[0]
            title = title_line.removeprefix("Title: ")
            return ProviderResult(
                output_text=(
                    '{"summary":"'
                    + title
                    + ' summary.","detail":"'
                    + title
                    + ' detail."}'
                ),
                provider_name="test",
            )

    repository = MarkdownKnowledgeRepository(tmp_path)
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=ChineseGateway(),
        auto_start=False,
    )
    job = jobs.submit_compile_job(
        question="流形与高维几何",
        anchors=[
            AnswerAnchor(anchor_id="流形的基本定义", label="流形的基本定义", status="pending"),
            AnswerAnchor(anchor_id="局部坐标图", label="局部坐标图", status="pending"),
            AnswerAnchor(anchor_id="切空间", label="切空间", status="pending"),
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="流形的基本定义",
                draft_type="definition",
                reason="Need a reusable definition.",
            ),
            PendingDraftRequest(
                title="局部坐标图",
                draft_type="definition",
                reason="Need a reusable definition.",
            ),
            PendingDraftRequest(
                title="切空间",
                draft_type="definition",
                reason="Need a reusable definition.",
            ),
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    completed = jobs.run_job(job.job_id)

    assert [anchor.node_id for anchor in completed.anchors] == [
        "流形的基本定义",
        "局部坐标图",
        "切空间",
    ]
    assert repository.get_node("流形的基本定义").summary == "流形的基本定义 summary."
    assert repository.get_node("局部坐标图").summary == "局部坐标图 summary."
    assert repository.get_node("切空间").summary == "切空间 summary."


def test_completed_knowledge_job_ensures_explorer_location(tmp_path: Path) -> None:
    class Gateway:
        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            return ProviderResult(
                output_text='{"summary":"A vector space summary.","detail":"A vector space detail."}',
                provider_name="test",
            )

    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=Gateway(),
        auto_start=False,
        explorer_store=explorer_store,
    )
    job = jobs.submit_compile_job(
        session_id="chat-1",
        question="What is a vector space?",
        anchors=[],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Vector Space",
                draft_type="definition",
                reason="Reusable definition.",
            )
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    jobs.run_job(job.job_id)

    node_id = repository.list_nodes()[0].id
    location = explorer_store.find_location("knowledge_node", node_id)
    assert location is not None
    assert location.location_source == "system"
    assert location.user_locked is False


def test_completed_knowledge_job_is_placed_in_selected_library_scope(
    tmp_path: Path,
) -> None:
    class Gateway:
        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            return ProviderResult(
                output_text='{"summary":"Scoped summary.","detail":"Scoped detail."}',
                provider_name="test",
            )

    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    _conversations, library = explorer_store.create_scope_root(
        name="Topology",
        primary_scope="sessions",
    )
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=Gateway(),
        auto_start=False,
        explorer_store=explorer_store,
    )
    job = jobs.submit_compile_job(
        session_id="chat-1",
        knowledge_scope_id=library.folder_id,
        question="What is a topology?",
        anchors=[],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Topology",
                draft_type="definition",
                reason="Reusable definition.",
            )
        ],
        provider_profile=ProviderProfile(
            provider_type="openai_compatible",
            model="test-model",
            credential_id="test",
        ),
    )

    completed = jobs.run_job(job.job_id)
    location = explorer_store.find_location(
        "knowledge_node",
        completed.anchors[0].node_id or "",
    )

    assert location is not None
    assert location.folder_id == library.folder_id


def test_same_knowledge_title_is_isolated_between_library_scopes(
    tmp_path: Path,
) -> None:
    class Gateway:
        def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
            return ProviderResult(
                output_text='{"summary":"Scoped summary.","detail":"Scoped detail."}',
                provider_name="test",
            )

    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    _first_conversations, first_library = explorer_store.create_scope_root(
        name="Course A",
        primary_scope="sessions",
    )
    _second_conversations, second_library = explorer_store.create_scope_root(
        name="Course B",
        primary_scope="sessions",
    )
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=Gateway(),
        auto_start=False,
        explorer_store=explorer_store,
    )
    profile = ProviderProfile(
        provider_type="openai_compatible",
        model="test-model",
        credential_id="test",
    )

    completed_jobs = []
    for library in (first_library, second_library):
        job = jobs.submit_compile_job(
            session_id="chat-1",
            knowledge_scope_id=library.folder_id,
            question="What is a group?",
            anchors=[],
            selected_node_ids=[],
            draft_requests=[
                PendingDraftRequest(
                    title="Group",
                    draft_type="definition",
                    reason="Reusable definition.",
                )
            ],
            provider_profile=profile,
        )
        completed_jobs.append(jobs.run_job(job.job_id))

    first_node_id = completed_jobs[0].anchors[0].node_id
    second_node_id = completed_jobs[1].anchors[0].node_id
    assert first_node_id == "group"
    assert second_node_id is not None
    assert second_node_id != first_node_id
    assert explorer_store.find_location(
        "knowledge_node",
        first_node_id or "",
    ).folder_id == first_library.folder_id
    assert explorer_store.find_location(
        "knowledge_node",
        second_node_id,
    ).folder_id == second_library.folder_id
