"""Deployment evidence must match the intended release, not just itself."""

import importlib.util
from pathlib import Path
import sys

import pytest


@pytest.fixture
def smoke(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts" / "prod_smoke.py"
    spec = importlib.util.spec_from_file_location("release_smoke_test", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setenv("SMARTWA_EXPECTED_MIGRATION_HEAD", "057")
    monkeypatch.setenv("SMARTWA_EXPECTED_COMMIT", "a" * 40)
    return module


@pytest.mark.parametrize("changes,ok", [
    ({}, True),
    ({"api_commit": "b" * 40, "worker_commit": "b" * 40}, False),
    ({"worker_commit": "b" * 40}, False),
    ({"api_commit": "unknown"}, False),
    ({"migration_heads": ["055", "057"]}, False),
    ({"migration_heads": ["055"]}, False),
    ({"worker_heartbeat_age_seconds": 121}, False),
    ({"worker_heartbeat_age_seconds": -1}, False),
    ({"worker_heartbeat_age_seconds": True}, False),
    ({"pipeline_health": None}, False),
    ({"pipeline_health": {"webhook_inbox": "ok", "operator_outbox": "attention", "ai_delivery": "ok"}}, False),
])
def test_release_alignment(smoke, monkeypatch, changes, ok):
    deployment = {
        "api_commit": "a" * 40, "worker_commit": "a" * 40,
        "migration_heads": ["057"], "worker_heartbeat_age_seconds": 20,
        "pipeline_health": {"webhook_inbox": "ok", "operator_outbox": "ok", "ai_delivery": "ok"},
        **changes,
    }
    monkeypatch.setattr(smoke, "_request", lambda _: (200, "", {"deployment": deployment}))
    assert smoke._check_deployment_alignment("https://backend.test").ok is ok


def test_repository_has_one_migration_head(smoke):
    assert smoke._repository_migration_head() == "057"
