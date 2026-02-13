import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.subscription_service import SubscriptionService
from app.core import n8n_security


def test_check_feature_returns_true_when_enabled():
    tenant_id = uuid.uuid4()
    plan = SimpleNamespace(feature_flags={"operator_takeover": True})
    subscription = SimpleNamespace(plan=plan)

    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = subscription

    db = MagicMock()
    db.query.return_value = query

    service = SubscriptionService(db)
    assert service.check_feature(tenant_id, "operator_takeover") is True


def test_check_feature_returns_false_without_subscription():
    tenant_id = uuid.uuid4()

    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = None

    db = MagicMock()
    db.query.return_value = query

    service = SubscriptionService(db)
    assert service.check_feature(tenant_id, "operator_takeover") is False


def test_message_limit_logs_event():
    tenant_id = uuid.uuid4()
    plan = SimpleNamespace(message_limit=5, name="starter")
    subscription = SimpleNamespace(
        plan=plan,
        messages_used_this_month=5,
        status="active",
        is_active=lambda: True
    )

    sub_query = MagicMock()
    sub_query.filter.return_value = sub_query
    sub_query.first.return_value = subscription

    event_query = MagicMock()
    event_query.filter.return_value = event_query
    event_query.first.return_value = None

    db = MagicMock()
    db.query.side_effect = [sub_query, event_query]

    service = SubscriptionService(db)

    with patch("app.services.subscription_service.SystemEventService.log") as log_mock:
        allowed, _ = service.check_message_limit(tenant_id)
        assert allowed is False
        log_mock.assert_called_once()
        _, kwargs = log_mock.call_args
        assert kwargs["code"] == "MESSAGE_LIMIT_EXCEEDED"


def test_verify_n8n_request_valid_signature():
    payload = {"hello": "world"}
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature, timestamp = n8n_security.generate_signature(payload_str, "secret")

    with patch.object(n8n_security.settings, "N8N_TO_SVONTAI_SECRET", "secret"):
        ok, error = n8n_security.verify_n8n_to_svontai_request(
            payload_str.encode(),
            signature,
            str(timestamp),
            "tenant-1"
        )
        assert ok is True
        assert error == ""


def test_verify_n8n_request_invalid_signature():
    payload = {"hello": "world"}
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    with patch.object(n8n_security.settings, "N8N_TO_SVONTAI_SECRET", "secret"):
        ok, error = n8n_security.verify_n8n_to_svontai_request(
            payload_str.encode(),
            "invalid",
            str(int(n8n_security.time.time())),
            "tenant-1"
        )
        assert ok is False
        assert "Invalid signature" in error
