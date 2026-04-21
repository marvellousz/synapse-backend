"""Email delivery helpers using Resend HTTP API."""

import logging
from html import escape

import httpx

from app.config import RESEND_API_KEY, RESEND_FROM_EMAIL

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class EmailDeliveryError(Exception):
    """Raised when email delivery provider rejects or fails a request."""

    def __init__(self, message: str, *, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def _render_shell(*, title: str, intro: str, cta_label: str, cta_url: str, note: str) -> str:
    safe_title = escape(title)
    safe_intro = escape(intro)
    safe_cta_label = escape(cta_label)
    safe_note = escape(note)
    safe_url = escape(cta_url, quote=True)

    return f"""
<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{safe_title}</title>
    </head>
    <body style="margin:0;padding:0;background:#f4f4f5;font-family:'Segoe UI',Arial,sans-serif;color:#111827;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:28px 12px;">
            <tr>
                <td align="center">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;">
                        <tr>
                            <td style="padding:0 0 10px 0;">
                                <span style="display:inline-block;background:#ffffff;border:2px solid #111827;padding:7px 12px;font-size:11px;letter-spacing:1.2px;font-weight:800;text-transform:uppercase;">synapse</span>
                            </td>
                        </tr>
                        <tr>
                            <td style="background:#ffffff;border:3px solid #111827;box-shadow:8px 8px 0 #111827;padding:28px;">
                                <h1 style="margin:0 0 10px 0;font-size:28px;line-height:1.2;letter-spacing:0.2px;">{safe_title}</h1>
                                <p style="margin:0 0 22px 0;font-size:16px;line-height:1.6;color:#374151;">{safe_intro}</p>
                                <a href="{safe_url}" style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;font-weight:800;letter-spacing:0.5px;text-transform:uppercase;padding:14px 18px;border:2px solid #111827;box-shadow:5px 5px 0 #111827;">
                                    {safe_cta_label}
                                </a>
                                <p style="margin:22px 0 8px 0;font-size:13px;line-height:1.6;color:#4b5563;">{safe_note}</p>
                                <p style="margin:0;font-size:12px;line-height:1.6;color:#6b7280;word-break:break-all;">
                                    button not working? copy this link:<br />
                                    <a href="{safe_url}" style="color:#4f46e5;">{safe_url}</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
</html>
""".strip()


def build_verify_email_html(*, verify_url: str) -> str:
    return _render_shell(
        title="Welcome to Synapse",
        intro="We are excited to have you! Please confirm your email address to get started.",
        cta_label="Confirm Email",
        cta_url=verify_url,
        note="This confirmation link expires in 24 hours.",
    )


def build_reset_password_email_html(*, reset_url: str) -> str:
    return _render_shell(
        title="reset your synapse password",
        intro="got locked out? no stress. use the button below to set a new password.",
        cta_label="reset password",
        cta_url=reset_url,
        note="this reset link expires in 24 hours.",
    )


def build_delete_account_email_html(*, delete_url: str) -> str:
    return _render_shell(
        title="confirm account deletion",
        intro="you requested to permanently delete your synapse account.",
        cta_label="delete account",
        cta_url=delete_url,
        note="this deletion link expires in 30 minutes. if this was not you, ignore this email.",
    )


async def send_email(*, to_email: str, subject: str, html: str) -> None:
    """Send an email via Resend. No-op if Resend is not configured."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY is not set; skipping outgoing email to %s", to_email)
        return

    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(RESEND_API_URL, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Email provider request failed") from exc

        if response.status_code >= 400:
            body_preview = response.text[:500]
            logger.error(
                "Resend rejected email (status=%s, to=%s, from=%s): %s",
                response.status_code,
                to_email,
                RESEND_FROM_EMAIL,
                body_preview,
            )
            raise EmailDeliveryError(
                "Email provider rejected request",
                status_code=response.status_code,
                response_body=body_preview,
            )
