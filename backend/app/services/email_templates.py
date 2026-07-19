"""Responsive, email-client-safe HTML templates for transactional messages."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any


def _safe(value: Any) -> str:
    return escape(str(value or ""), quote=True)


def _layout(*, preheader: str, eyebrow: str, title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="tr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="x-apple-disable-message-reformatting">
    <title>{_safe(title)}</title>
  </head>
  <body style="margin:0;padding:0;background:#f3f6fa;color:#101828;font-family:Arial,Helvetica,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{_safe(preheader)}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f6fa;">
      <tr>
        <td align="center" style="padding:32px 12px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background:#ffffff;border:1px solid #e4e7ec;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="background:#101828;padding:24px 28px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td style="font-size:23px;line-height:28px;font-weight:700;color:#ffffff;">Svont<span style="color:#22d3ee;">AI</span></td>
                    <td align="right" style="font-size:10px;line-height:14px;font-weight:700;color:#a5f3fc;text-transform:uppercase;">Otonom işletme asistanı</td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:32px 28px 12px;">
                <div style="font-size:11px;line-height:16px;font-weight:700;color:#0e7490;text-transform:uppercase;">{_safe(eyebrow)}</div>
                <h1 style="margin:8px 0 0;font-size:28px;line-height:36px;font-weight:700;color:#101828;">{_safe(title)}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:12px 28px 32px;">{content}</td>
            </tr>
            <tr>
              <td style="border-top:1px solid #eaecf0;padding:22px 28px;background:#f9fafb;">
                <p style="margin:0;font-size:12px;line-height:18px;color:#667085;">Bu e-posta SvontAI tarafından otomatik olarak gönderildi.</p>
                <p style="margin:4px 0 0;font-size:12px;line-height:18px;color:#98a2b3;">© 2026 SvontAI · Güvenli ve otonom müşteri iletişimi</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def render_verification_email(
    *,
    full_name: str,
    email: str,
    code: str,
    expire_minutes: int,
    verification_url: str,
) -> str:
    content = f"""
      <p style="margin:0 0 12px;font-size:16px;line-height:25px;color:#344054;">Merhaba {_safe(full_name)},</p>
      <p style="margin:0 0 24px;font-size:15px;line-height:24px;color:#475467;">Hesabınızı kullanmaya başlamak için aşağıdaki doğrulama kodunu SvontAI ekranına girin.</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 20px;">
        <tr>
          <td align="center" style="padding:24px;background:#ecfeff;border:1px solid #a5f3fc;border-radius:8px;">
            <div style="font-size:11px;line-height:16px;font-weight:700;color:#0e7490;text-transform:uppercase;">Doğrulama kodunuz</div>
            <div style="margin-top:8px;font-family:'Courier New',monospace;font-size:36px;line-height:44px;font-weight:700;letter-spacing:8px;color:#101828;">{_safe(code)}</div>
            <div style="margin-top:8px;font-size:13px;line-height:18px;color:#475467;">Kod {_safe(expire_minutes)} dakika geçerlidir.</div>
          </td>
        </tr>
      </table>
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 auto 24px;">
        <tr>
          <td align="center" bgcolor="#0e7490" style="border-radius:6px;">
            <a href="{_safe(verification_url)}" style="display:inline-block;padding:13px 22px;font-size:14px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;">Doğrulama ekranını aç</a>
          </td>
        </tr>
      </table>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
          <td style="padding:14px 16px;background:#f9fafb;border-left:3px solid #98a2b3;">
            <p style="margin:0;font-size:13px;line-height:20px;color:#475467;"><strong style="color:#344054;">Güvenlik notu:</strong> Bu kod yalnızca {_safe(email)} adresi için üretildi. SvontAI ekibi sizden bu kodu telefon veya mesaj yoluyla istemez.</p>
          </td>
        </tr>
      </table>
      <p style="margin:20px 0 0;font-size:13px;line-height:20px;color:#667085;">Bu işlemi siz başlatmadıysanız e-postayı güvenle yok sayabilirsiniz.</p>
    """
    return _layout(
        preheader="SvontAI hesabınızı doğrulamak için kodunuz hazır.",
        eyebrow="Hesap güvenliği",
        title="E-posta adresinizi doğrulayın",
        content=content,
    )


def _metric_cell(label: str, value: Any, accent: str = "#0e7490") -> str:
    return f"""
      <td width="50%" valign="top" style="padding:5px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
          <tr>
            <td style="padding:16px;background:#f9fafb;border:1px solid #eaecf0;border-radius:6px;">
              <div style="font-size:12px;line-height:17px;color:#667085;">{_safe(label)}</div>
              <div style="margin-top:5px;font-size:24px;line-height:30px;font-weight:700;color:{accent};">{_safe(value)}</div>
            </td>
          </tr>
        </table>
      </td>
    """


def render_operational_report_email(*, report: dict, dashboard_url: str) -> str:
    metrics = report.get("metrics") or {}
    incoming = int(metrics.get("incoming_messages") or 0)
    replies = int(metrics.get("ai_replies") or 0)
    failed = int(metrics.get("failed_automations") or 0)
    healthy = failed == 0 and (incoming == 0 or replies > 0)
    period_label = "Haftalık operasyon raporu" if report.get("period") == "week" else "Günlük operasyon raporu"
    status_title = "Sistem sağlıklı çalışıyor" if healthy else "Kontrol edilmesi gereken durum var"
    status_text = (
        "SvontAI müşteri iletişimini ve otomasyonları izlemeye devam ediyor."
        if healthy
        else "Yanıt veya otomasyon metriklerinde dikkat gerektiren bir durum algılandı."
    )
    status_color = "#027a48" if healthy else "#b54708"
    status_background = "#ecfdf3" if healthy else "#fffaeb"
    generated_at = str(report.get("generated_at") or "")
    try:
        generated_at = datetime.fromisoformat(generated_at).strftime("%d.%m.%Y · %H:%M")
    except ValueError:
        pass

    content = f"""
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 22px;">
        <tr>
          <td style="padding:16px;background:{status_background};border-left:4px solid {status_color};">
            <div style="font-size:15px;line-height:21px;font-weight:700;color:{status_color};">{_safe(status_title)}</div>
            <div style="margin-top:4px;font-size:13px;line-height:20px;color:#475467;">{_safe(status_text)}</div>
          </td>
        </tr>
      </table>
      <p style="margin:0 0 10px;font-size:13px;line-height:19px;font-weight:700;color:#344054;">Performans özeti</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 -5px 18px;">
        <tr>
          {_metric_cell("Gelen mesaj", incoming)}
          {_metric_cell("Otomatik AI yanıtı", replies)}
        </tr>
        <tr>
          {_metric_cell("Yanıt oranı", f"%{metrics.get('response_rate', 0)}")}
          {_metric_cell("Yeni müşteri", metrics.get('leads', 0))}
        </tr>
        <tr>
          {_metric_cell("Randevu", metrics.get('appointments', 0))}
          {_metric_cell("Yeni konuşma", metrics.get('conversations', 0))}
        </tr>
      </table>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 22px;">
        <tr>
          <td style="padding:15px 16px;background:#f9fafb;border:1px solid #eaecf0;border-radius:6px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
              <tr>
                <td style="font-size:13px;line-height:20px;color:#475467;">Başarılı otomasyon</td>
                <td align="right" style="font-size:14px;line-height:20px;font-weight:700;color:#027a48;">{_safe(metrics.get('successful_automations', 0))}</td>
              </tr>
              <tr>
                <td style="padding-top:8px;font-size:13px;line-height:20px;color:#475467;">Hatalı otomasyon</td>
                <td align="right" style="padding-top:8px;font-size:14px;line-height:20px;font-weight:700;color:{'#b42318' if failed else '#344054'};">{_safe(failed)}</td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
      <div style="padding:18px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;">
        <div style="font-size:12px;line-height:17px;font-weight:700;color:#0369a1;text-transform:uppercase;">Kısa özet</div>
        <p style="margin:6px 0 0;font-size:14px;line-height:22px;color:#344054;">{_safe(report.get('summary'))}</p>
      </div>
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:24px auto 20px;">
        <tr>
          <td align="center" bgcolor="#0e7490" style="border-radius:6px;">
            <a href="{_safe(dashboard_url)}" style="display:inline-block;padding:13px 22px;font-size:14px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;">Kontrol panelini aç</a>
          </td>
        </tr>
      </table>
      <p style="margin:0;text-align:center;font-size:12px;line-height:18px;color:#98a2b3;">{_safe(generated_at)} · {_safe(report.get('timezone'))}</p>
    """
    return _layout(
        preheader=str(report.get("summary") or "SvontAI operasyon raporunuz hazır."),
        eyebrow=period_label,
        title=str(report.get("title") or "SvontAI operasyon raporu"),
        content=content,
    )
