from app.core.config import settings
from app.services import email_service as email_service_module
from app.services.email_service import EmailService
from app.services.email_templates import (
    render_operational_report_email,
    render_verification_email,
)


def _report() -> dict:
    return {
        "period": "today",
        "title": "Doğüncü İşletmesi - SvontAI Bugün Raporu",
        "summary": "12 müşteri mesajı alındı, 11 otomatik yanıt gönderildi.",
        "text": "Plain text report",
        "generated_at": "2026-07-20T18:00:00+03:00",
        "timezone": "Europe/Istanbul",
        "metrics": {
            "incoming_messages": 12,
            "ai_replies": 11,
            "response_rate": 91.7,
            "conversations": 7,
            "leads": 3,
            "appointments": 2,
            "successful_automations": 5,
            "failed_automations": 0,
        },
    }


def test_verification_template_is_branded_and_escapes_user_content():
    html = render_verification_email(
        full_name="<script>alert(1)</script>",
        email="owner@example.com",
        code="482193",
        expire_minutes=10,
        verification_url="https://svontai.example/verify-email?email=owner%40example.com",
    )

    assert "E-posta adresinizi doğrulayın" in html
    assert "482193" in html
    assert "Svont<span" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "https://svontai.example/verify-email?email=owner%40example.com" in html


def test_operational_report_template_uses_real_metrics():
    html = render_operational_report_email(
        report=_report(),
        dashboard_url="https://svontai.example/dashboard",
    )

    assert "Günlük operasyon raporu" in html
    assert "Sistem sağlıklı çalışıyor" in html
    assert "Gelen mesaj" in html and ">12<" in html
    assert "Otomatik AI yanıtı" in html and ">11<" in html
    assert "%91.7" in html
    assert "20.07.2026 · 18:00" in html
    assert "https://svontai.example/dashboard" in html


def test_resend_payload_contains_plain_text_and_html(monkeypatch):
    captured = {}

    class Response:
        is_success = True
        status_code = 200
        text = "ok"

    def fake_post(*args, **kwargs):
        captured.update(kwargs["json"])
        return Response()

    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-resend-key")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://svontai.example")
    monkeypatch.setattr(email_service_module.httpx, "post", fake_post)

    sent = EmailService.send_email_verification_code(
        email="owner@example.com",
        full_name="Süleyman",
        code="123456",
        expire_minutes=10,
    )

    assert sent is True
    assert captured["text"].startswith("Merhaba Süleyman")
    assert "123456" in captured["html"]
    assert "https://svontai.example/verify-email?email=owner%40example.com" in captured["html"]


def test_operational_report_sender_preserves_plain_text_fallback(monkeypatch):
    captured = {}

    def fake_send_email(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(settings, "FRONTEND_URL", "https://svontai.example")
    monkeypatch.setattr(EmailService, "send_email", staticmethod(fake_send_email))

    sent = EmailService.send_operational_report_email(
        recipients="owner@example.com",
        report=_report(),
    )

    assert sent is True
    assert captured["text_body"] == "Plain text report"
    assert "Kontrol panelini aç" in captured["html_body"]
    assert captured["subject"] == "Doğüncü İşletmesi - SvontAI Bugün Raporu"
