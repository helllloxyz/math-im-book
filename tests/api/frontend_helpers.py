from __future__ import annotations

import re

from fastapi.testclient import TestClient


def fetch_frontend_bundle(client: TestClient) -> tuple[str, str, str, str]:
    html_response = client.get("/")
    assert html_response.status_code == 200
    html = html_response.text

    js_match = re.search(r'src="(/assets/[^"]+\.js)"', html)
    css_match = re.search(r'href="(/assets/[^"]+\.css)"', html)
    assert js_match is not None
    assert css_match is not None

    js_path = js_match.group(1)
    css_path = css_match.group(1)
    js_response = client.get(js_path)
    css_response = client.get(css_path)

    assert js_response.status_code == 200
    assert css_response.status_code == 200

    return html, js_path, css_path, js_response.text
