from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import AnswerAnchor, KnowledgeNode, NodeReference
from math_im_book.services.knowledge_jobs import InMemoryKnowledgeJobRepository
from math_im_book.storage.sessions import FileSessionStore, SessionMessage, SessionRecord
from math_im_book.storage.markdown import MarkdownKnowledgeRepository


def test_outline_endpoint_lists_knowledge_nodes(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="vector-space",
            title="Vector Space",
            type="atomic",
            summary="A vector space is closed under addition and scalar multiplication.",
            detail="Detailed definition of a vector space.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
            symbols={"V": "vector space"},
            symbol_scopes={
                "global": {"V": "vector space"},
                "local": {"v": "vector in V"},
            },
        )
    )
    client = TestClient(create_app(repository=repository))

    response = client.get("/api/outline")

    assert response.status_code == 200
    assert response.json()["nodes"][0]["id"] == "vector-space"


def test_node_endpoint_returns_node_detail(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="vector-space",
            title="Vector Space",
            type="atomic",
            summary="A vector space is closed under addition and scalar multiplication.",
            detail="Detailed definition of a vector space.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
            symbols={"V": "vector space"},
            symbol_scopes={
                "global": {"V": "vector space"},
                "local": {"v": "vector in V"},
            },
        )
    )
    client = TestClient(create_app(repository=repository))

    response = client.get("/api/nodes/vector-space")

    assert response.status_code == 200
    assert response.json()["node"]["title"] == "Vector Space"
    assert response.json()["node"]["symbol_scopes"] == {
        "global": {"V": "vector space"},
        "local": {"v": "vector in V"},
    }


def test_node_endpoint_returns_reference_reasons_for_navigation(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="A linear map preserves addition and scalar multiplication.",
            detail="Detailed definition of a linear map.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="kernel",
            title="Kernel",
            type="atomic",
            summary="The kernel contains vectors mapped to zero.",
            detail="Detailed definition of the kernel.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="rank-nullity",
            title="Rank-Nullity Theorem",
            type="atomic",
            summary="Relates rank and nullity.",
            detail="Detailed statement of the theorem.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="matrix-representation",
            title="Matrix Representation",
            type="atomic",
            summary="Represents a linear map with coordinates.",
            detail="Detailed matrix representation discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="dimension-theorem",
            title="Dimension Theorem",
            type="atomic",
            summary="A consequence of rank-nullity.",
            detail="Detailed discussion of dimension theorem.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="linear-operator",
            title="Linear Operator",
            type="atomic",
            summary="An endomorphism on a vector space.",
            detail="Detailed operator discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="vector-space",
            title="Vector Space",
            type="atomic",
            summary="A space closed under addition and scalar multiplication.",
            detail="Detailed definition of a vector space.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="basis",
            title="Basis",
            type="atomic",
            summary="A minimal spanning set.",
            detail="Detailed basis definition.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="isomorphism",
            title="Isomorphism",
            type="atomic",
            summary="A bijective linear map.",
            detail="Detailed isomorphism definition.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="quotient-space",
            title="Quotient Space",
            type="atomic",
            summary="A space modulo a subspace.",
            detail="Detailed quotient space definition.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="eigenvalue",
            title="Eigenvalue",
            type="atomic",
            summary="A scalar associated with an eigenvector.",
            detail="Detailed eigenvalue definition.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="spectral-theorem",
            title="Spectral Theorem",
            type="atomic",
            summary="Diagonalization under suitable hypotheses.",
            detail="Detailed spectral theorem discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="change-of-basis",
            title="Change of Basis",
            type="atomic",
            summary="Transforms coordinate representations.",
            detail="Detailed change of basis discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="coordinate-map",
            title="Coordinate Map",
            type="atomic",
            summary="Maps vectors to coordinates.",
            detail="Detailed coordinate map discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="invariant-subspace",
            title="Invariant Subspace",
            type="atomic",
            summary="A subspace preserved by an operator.",
            detail="Detailed invariant subspace discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="vector-space-map",
            title="Vector Space Map",
            type="atomic",
            summary="Relates vector spaces and linear maps.",
            detail="Detailed bridge discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="operator-kernel-link",
            title="Operator Kernel Link",
            type="atomic",
            summary="Connects operators and kernels.",
            detail="Detailed operator-kernel discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="node-with-references",
            title="Node With References",
            type="atomic",
            summary="Node used to test navigation references.",
            detail="Detailed node with references.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[
                NodeReference(
                    node_id="linear-map",
                    reason="Uses the definition of a linear map.",
                ),
                NodeReference(
                    node_id="kernel",
                    reason="Builds on the kernel construction.",
                ),
            ],
            status="ready",
        )
    )
    client = TestClient(create_app(repository=repository))

    response = client.get("/api/nodes/node-with-references")

    assert response.status_code == 200
    assert response.json()["node"]["references"] == [
        {"node_id": "linear-map", "reason": "Uses the definition of a linear map."},
        {"node_id": "kernel", "reason": "Builds on the kernel construction."},
    ]


def test_node_endpoint_returns_incoming_references_for_reverse_navigation(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="A linear map preserves addition and scalar multiplication.",
            detail="Detailed definition of a linear map.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="kernel",
            title="Kernel",
            type="atomic",
            summary="The kernel contains vectors mapped to zero.",
            detail="Detailed definition of the kernel.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="operator-kernel-link",
            title="Operator Kernel Link",
            type="atomic",
            summary="Connects operators and kernels.",
            detail="Detailed operator-kernel discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[
                NodeReference(
                    node_id="linear-map",
                    reason="Uses the definition of a linear map.",
                ),
                NodeReference(
                    node_id="kernel",
                    reason="Builds on the kernel construction.",
                ),
            ],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="matrix-representation",
            title="Matrix Representation",
            type="atomic",
            summary="Represents a linear map with coordinates.",
            detail="Detailed matrix representation discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[
                NodeReference(
                    node_id="linear-map",
                    reason="Turns a linear map into coordinates.",
                )
            ],
            status="ready",
        )
    )
    client = TestClient(create_app(repository=repository))

    response = client.get("/api/nodes/linear-map")

    assert response.status_code == 200
    assert response.json()["node"]["incoming_references"] == [
        {
            "node_id": "matrix-representation",
            "reason": "Turns a linear map into coordinates.",
        },
        {
            "node_id": "operator-kernel-link",
            "reason": "Uses the definition of a linear map.",
        },
    ]


def test_node_endpoint_returns_display_references_and_related_discussions(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="session-1",
            title="Linear algebra warmup",
            messages=[
                SessionMessage(role="user", content="What makes a map linear?"),
                SessionMessage(role="assistant", content="It preserves addition and scalar multiplication."),
            ],
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="vector-space",
            title="Vector Space",
            type="atomic",
            summary="Defines the ambient space.",
            detail="Detailed vector space definition.",
            parent_id="linear-algebra",
            source="session-1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves vector operations.",
            detail="Detailed linear map definition.",
            parent_id="linear-algebra",
            source="session-1",
            references=[
                NodeReference(
                    node_id="vector-space",
                    reason="Uses vector spaces for domain and codomain.",
                )
            ],
            status="ready",
        )
    )
    client = TestClient(create_app(repository=repository, session_store=session_store))

    response = client.get("/api/nodes/linear-map")

    assert response.status_code == 200
    payload = response.json()["node"]
    assert payload["references_display"] == [
        {
            "node_id": "vector-space",
            "title": "Vector Space",
            "summary": "Defines the ambient space.",
            "reason": "Uses vector spaces for domain and codomain.",
            "type": "atomic",
            "status": "ready",
        }
    ]
    assert payload["related_session_ids"] == ["session-1"]
    assert payload["related_discussions"] == [
        {
            "session_id": "session-1",
            "title": "Linear algebra warmup",
            "preview": "It preserves addition and scalar multiplication.",
            "message_count": 2,
            "focus_question": None,
        }
    ]


def test_knowledge_job_response_includes_error_message(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(repository, auto_start=False)
    job = knowledge_jobs.submit_compile_job(
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
    )
    stored = knowledge_jobs._jobs[job.job_id]
    stored.status = "failed"
    stored.error_message = "provider unavailable"
    stored.anchors[0].status = "failed"

    client = TestClient(
        create_app(
            repository=repository,
            knowledge_job_repository=knowledge_jobs,
        )
    )

    response = client.get(f"/api/knowledge-jobs/{job.job_id}")

    assert response.status_code == 200
    assert response.json()["error_message"] == "provider unavailable"
