from __future__ import annotations

import re
from pathlib import Path


def _canonical_path(path: str) -> str:
    path = path.strip()
    path = re.sub(r"\{[^}]+\}", "{param}", path)
    path = re.sub(r"\$\{[^}]+\}", "{param}", path)
    return path


def _extract_frontend_api_calls(source: str) -> set[tuple[str, str]]:
    calls: set[tuple[str, str]] = set()

    # api.get('/path')
    single_quote = re.compile(r"\bapi\.(get|post|put|patch|delete)\(\s*'([^']+)'", re.IGNORECASE)
    for method, path in single_quote.findall(source):
        calls.add((method.upper(), _canonical_path(path)))

    # api.get(`/path/${id}`)
    template = re.compile(r"\bapi\.(get|post|put|patch|delete)\(\s*`([^`]+)`", re.IGNORECASE)
    for method, path in template.findall(source):
        calls.add((method.upper(), _canonical_path(path)))

    # axios.post(`${API_URL}/auth/refresh`, ...)
    axios_template = re.compile(r"\baxios\.(get|post|put|patch|delete)\(\s*`\$\{API_URL\}([^`]+)`", re.IGNORECASE)
    for method, path in axios_template.findall(source):
        calls.add((method.upper(), _canonical_path(path)))

    return calls


def test_frontend_api_ts_matches_backend_routes(client):
    repo_root = Path(__file__).resolve().parents[2]
    api_ts_path = repo_root / "frontend" / "src" / "lib" / "api.ts"
    source = api_ts_path.read_text(encoding="utf-8")

    frontend_calls = _extract_frontend_api_calls(source)
    assert frontend_calls, "No frontend API calls extracted; parser may be broken."

    available: set[tuple[str, str]] = set()
    for route in client.app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        canonical = _canonical_path(path)
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            available.add((method.upper(), canonical))

    missing: list[str] = []
    for method, path in sorted(frontend_calls):
        if (method, path) not in available:
            missing.append(f"{method} {path}")

    assert not missing, "Frontend api.ts contains missing backend routes:\\n" + "\\n".join(missing)
