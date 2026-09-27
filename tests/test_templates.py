from starlette.requests import Request

from app.main import _page


def _request(path: str = "/") -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", 8000),
        }
    )


def test_login_page_renders_with_starlette_template_signature():
    response = _page("login.html", _request("/login"), {"title": "Sign in"})
    assert response.status_code == 200
    assert b"Pingwatch" in response.body


def test_dashboard_template_renders():
    response = _page(
        "index.html",
        _request("/"),
        {"title": "Uptime", "nav": "dashboard", "lede": "Monitor NAS, storage, and server availability."},
    )
    assert response.status_code == 200
    assert b"Internal Server Error" not in response.body
