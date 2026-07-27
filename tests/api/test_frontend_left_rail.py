from fastapi.testclient import TestClient

from math_im_book.api.app import create_app

from tests.api.frontend_helpers import fetch_frontend_bundle


def test_frontend_page_no_longer_server_renders_branch_focus_panel() -> None:
    client = TestClient(create_app())

    html, _, _, _ = fetch_frontend_bundle(client)

    assert 'id="branch-focus-panel"' not in html
    assert 'id="conversation-branch-header"' not in html
