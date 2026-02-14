"""
Email delivery service for transactional notifications.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Sequence

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Handles SMTP email sending and common templates."""

    @staticmethod
    def _normalize_recipients(recipients: str | Sequence[str]) -> list[str]:
        if isinstance(recipients, str):
            value = recipients.strip()
            return [value] if value else []
        return [item.strip() for item in recipients if item and item.strip()]

    @staticmethod
    def send_email(
        recipients: str | Sequence[str],
        subject: str,
        text_body: str
    ) -> bool:
        """Send an email. Returns False when disabled or on failure."""
        normalized = EmailService._normalize_recipients(recipients)
        if not normalized:
            return False

        if not settings.EMAIL_ENABLED:
            logger.info(
                "Email disabled, skipped send",
                extra={"to": normalized, "subject": subject}
            )
            return False

        if settings.EMAIL_PROVIDER == "resend":
            return EmailService._send_via_resend(
                recipients=normalized,
                subject=subject,
                text_body=text_body
            )

        return EmailService._send_via_smtp(
            recipients=normalized,
            subject=subject,
            text_body=text_body
        )

    @staticmethod
    def _send_via_resend(
        recipients: list[str],
        subject: str,
        text_body: str
    ) -> bool:
        api_key = settings.RESEND_API_KEY.strip()
        if not api_key:
            logger.warning("Resend API key is missing, email not sent")
            return False

        from_name = settings.SMTP_FROM_NAME.strip()
        from_email = settings.SMTP_FROM_EMAIL.strip()
        from_value = f"{from_name} <{from_email}>" if from_name else from_email
        endpoint = f"{settings.RESEND_API_BASE_URL.rstrip('/')}/emails"
        payload = {
            "from": from_value,
            "to": recipients,
            "subject": subject,
            "text": text_body,
        }

        try:
            response = httpx.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=settings.RESEND_TIMEOUT_SECONDS
            )
            if response.is_success:
                return True
            logger.warning(
                "Resend email failed (status=%s): %s",
                response.status_code,
                response.text[:500]
            )
            return False
        except Exception as exc:
            logger.warning("Resend request error: %s", exc)
            return False

    @staticmethod
    def _send_via_smtp(
        recipients: list[str],
        subject: str,
        text_body: str
    ) -> bool:
        message = EmailMessage()
        from_name = settings.SMTP_FROM_NAME.strip()
        from_email = settings.SMTP_FROM_EMAIL.strip()
        message["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(text_body)

        try:
            if settings.SMTP_USE_SSL:
                with smtplib.SMTP_SSL(
                    host=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT_SECONDS
                ) as smtp:
                    EmailService._authenticate(smtp)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(
                    host=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT_SECONDS
                ) as smtp:
                    if settings.SMTP_USE_TLS:
                        smtp.starttls()
                    EmailService._authenticate(smtp)
                    smtp.send_message(message)
            return True
        except Exception as exc:
            logger.warning(
                "Email send failed",
                extra={"to": recipients, "subject": subject, "error": str(exc)}
            )
            return False

    @staticmethod
    def _authenticate(smtp: smtplib.SMTP) -> None:
        username = settings.SMTP_USERNAME.strip()
        if username:
            smtp.login(username, settings.SMTP_PASSWORD)

    @staticmethod
    def send_password_reset_code(
        email: str,
        full_name: str,
        code: str,
        expire_minutes: int
    ) -> bool:
        subject = "SvontAI şifre sıfırlama kodunuz"
        text = (
            f"Merhaba {full_name},\n\n"
            f"Şifre sıfırlama kodunuz: {code}\n"
            f"Bu kod {expire_minutes} dakika boyunca geçerlidir.\n\n"
            "Eğer bu işlemi siz yapmadıysanız bu e-postayı dikkate almayın.\n\n"
            "SvontAI"
        )
        return EmailService.send_email(email, subject, text)

    @staticmethod
    def send_password_changed_confirmation(email: str, full_name: str) -> bool:
        subject = "SvontAI şifreniz güncellendi"
        text = (
            f"Merhaba {full_name},\n\n"
            "Hesabınızın şifresi başarıyla değiştirildi.\n"
            "Bu işlemi siz yapmadıysanız hemen destek ile iletişime geçin.\n\n"
            "SvontAI"
        )
        return EmailService.send_email(email, subject, text)

    @staticmethod
    def send_welcome_email(email: str, full_name: str) -> bool:
        subject = "SvontAI hesabınız oluşturuldu"
        text = (
            f"Merhaba {full_name},\n\n"
            "SvontAI hesabınız başarıyla oluşturuldu.\n"
            "Panelinize giriş yaparak kurulum adımlarını tamamlayabilirsiniz.\n\n"
            "SvontAI"
        )
        return EmailService.send_email(email, subject, text)

    @staticmethod
    def send_email_verification_code(
        email: str,
        full_name: str,
        code: str,
        expire_minutes: int
    ) -> bool:
        subject = "SvontAI e-posta doğrulama kodunuz"
        text = (
            f"Merhaba {full_name},\n\n"
            "SvontAI hesabınızı doğrulamak için aşağıdaki kodu kullanın:\n\n"
            f"{code}\n\n"
            f"Bu kod {expire_minutes} dakika boyunca geçerlidir.\n\n"
            "Eğer bu işlemi siz yapmadıysanız bu e-postayı dikkate almayın.\n\n"
            "SvontAI"
        )
        return EmailService.send_email(email, subject, text)

    @staticmethod
    def send_plan_change_email(
        email: str,
        full_name: str,
        tenant_name: str,
        plan_display_name: str,
        action: str
    ) -> bool:
        subject = f"SvontAI plan güncellemesi: {plan_display_name}"
        text = (
            f"Merhaba {full_name},\n\n"
            f"{tenant_name} hesabı için plan işlemi gerçekleştirildi: {action}\n"
            f"Yeni plan: {plan_display_name}\n\n"
            "Bu değişiklik size ait değilse destek ekibine başvurun.\n\n"
            "SvontAI"
        )
        return EmailService.send_email(email, subject, text)

    @staticmethod
    def send_appointment_created_email(
        email: str,
        customer_name: str,
        subject_title: str,
        starts_at_label: str
    ) -> bool:
        subject = f"Randevu oluşturuldu: {subject_title}"
        text = (
            f"Merhaba {customer_name},\n\n"
            f"Randevunuz oluşturuldu.\n"
            f"Konu: {subject_title}\n"
            f"Tarih/Saat: {starts_at_label}\n\n"
            "Randevu öncesi ek bilgilendirme alacaksınız.\n\n"
            "SvontAI"
        )
        return EmailService.send_email(email, subject, text)

    @staticmethod
    def send_appointment_before_reminder_email(
        email: str,
        customer_name: str,
        subject_title: str,
        starts_at_label: str
    ) -> bool:
        subject = f"Randevu hatırlatma: {subject_title}"
        text = (
            f"Merhaba {customer_name},\n\n"
            "Randevunuz yaklaşıyor.\n"
            f"Konu: {subject_title}\n"
            f"Tarih/Saat: {starts_at_label}\n\n"
            "SvontAI"
        )
        return EmailService.send_email(email, subject, text)

    @staticmethod
    def send_appointment_after_followup_email(
        email: str,
        customer_name: str,
        subject_title: str
    ) -> bool:
        subject = f"Randevu sonrası bilgilendirme: {subject_title}"
        text = (
            f"Merhaba {customer_name},\n\n"
            f"{subject_title} randevunuz tamamlandı.\n"
            "Geri bildirim ve sonraki adımlar için panelinizi kontrol edebilirsiniz.\n\n"
            "SvontAI"
        )
        return EmailService.send_email(email, subject, text)
