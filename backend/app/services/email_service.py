from decimal import Decimal
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
FROM_EMAIL = "noreply@gstsense.in"
FROM_NAME = "GSTSense"

_BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
  .container {{ max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; }}
  .header {{ background: #534AB7; padding: 24px 32px; }}
  .logo {{ color: #ffffff; font-size: 22px; font-weight: bold; letter-spacing: 0.5px; }}
  .body {{ padding: 32px; color: #444441; }}
  h2 {{ color: #534AB7; }}
  .btn {{ display: inline-block; background: #534AB7; color: #ffffff !important;
         text-decoration: none; padding: 12px 28px; border-radius: 6px;
         font-weight: bold; font-size: 15px; margin: 20px 0; }}
  .stat-box {{ background: #F1EFE8; border-radius: 6px; padding: 16px 24px; margin: 16px 0; }}
  .stat-label {{ font-size: 12px; color: #888; }}
  .stat-value {{ font-size: 22px; font-weight: bold; color: #E24B4A; }}
  .footer {{ background: #f9f9f9; padding: 16px 32px; font-size: 11px; color: #888; border-top: 1px solid #eee; }}
  .disclaimer {{ font-style: italic; font-size: 10px; color: #999; margin-top: 8px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header"><div class="logo">GSTSense</div></div>
  <div class="body">{body}</div>
  <div class="footer">
    <div>© 2024 GSTSense · gstsense.in</div>
    <div class="disclaimer">
      This email is generated for informational purposes only. All findings must be
      verified with your Chartered Accountant. GSTSense does not constitute legal or tax advice.
    </div>
  </div>
</div>
</body>
</html>
"""


def _wrap(body: str) -> str:
    return _BASE_HTML.format(body=body)


class EmailService:
    def __init__(self) -> None:
        self.api_key = settings.RESEND_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_welcome_email(
        self,
        to_email: str,
        full_name: str,
        business_name: str,
    ) -> bool:
        """Send welcome email after registration."""
        subject = f"Welcome to GSTSense, {full_name}!"
        body = f"""
        <h2>Welcome to GSTSense! 🎉</h2>
        <p>Hi {full_name},</p>
        <p>Your account for <strong>{business_name}</strong> is ready. Here's what you can do:</p>
        <ol>
          <li><strong>Scan your GSTR files</strong> — Upload GSTR-1 and GSTR-3B to detect mismatches instantly.</li>
          <li><strong>Check your ITC</strong> — See exactly how much Input Tax Credit you may be losing.</li>
          <li><strong>Prepare for notices</strong> — Get AI-powered explanations before the GST department does.</li>
        </ol>
        <a href="https://gstsense.in/scan" class="btn">Start Your First Scan</a>
        <p style="color:#888;font-size:12px;">Your first scan is free. No credit card required.</p>
        """
        return await self._send(to_email, subject, _wrap(body))

    async def send_scan_complete_email(
        self,
        to_email: str,
        full_name: str,
        business_name: str,
        scan_month: str,
        total_mismatches: int,
        total_rupee_risk: Decimal,
        scan_id: str,
    ) -> bool:
        """Send email when scan is complete."""
        from datetime import datetime
        try:
            dt = datetime.strptime(scan_month, "%Y-%m")
            month_label = dt.strftime("%B %Y")
        except ValueError:
            month_label = scan_month

        subject = f"Your GST Scan is Ready — {total_mismatches} mismatches found"
        urgency = ""
        if total_mismatches > 0:
            urgency = (
                f"<p style='color:#E24B4A;'><strong>⚠️ Action Required:</strong> "
                f"These mismatches can trigger automated Rule 88C notices from the GST department. "
                f"Please review and correct them before your next filing deadline.</p>"
            )
        body = f"""
        <h2>Your {month_label} Scan is Complete</h2>
        <p>Hi {full_name},</p>
        <p>We've finished scanning the GSTR files for <strong>{business_name}</strong>.</p>
        <div class="stat-box">
          <div class="stat-label">Mismatches Found</div>
          <div class="stat-value">{total_mismatches}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Total Rupee Risk</div>
          <div class="stat-value">₹{total_rupee_risk:,.2f}</div>
        </div>
        {urgency}
        <a href="https://gstsense.in/scan/report/{scan_id}" class="btn">View Full Report</a>
        """
        return await self._send(to_email, subject, _wrap(body))

    async def send_password_reset_email(
        self,
        to_email: str,
        full_name: str,
        reset_token: str,
    ) -> bool:
        """Send password reset email."""
        reset_url = f"https://gstsense.in/reset-password?token={reset_token}"
        subject = "Reset your GSTSense password"
        body = f"""
        <h2>Reset Your Password</h2>
        <p>Hi {full_name},</p>
        <p>We received a request to reset the password for your GSTSense account.</p>
        <a href="{reset_url}" class="btn">Reset Password</a>
        <p style="color:#888;font-size:12px;">
          This link expires in <strong>1 hour</strong>. If you did not request a password reset,
          you can safely ignore this email — your password will not change.
        </p>
        <p style="word-break:break-all;font-size:11px;color:#aaa;">
          If the button above doesn't work, copy this URL into your browser:<br>{reset_url}
        </p>
        """
        return await self._send(to_email, subject, _wrap(body))

    async def _send(self, to_email: str, subject: str, html_body: str) -> bool:
        """Send via Resend API. Returns True on success, never raises."""
        payload = {
            "from": f"{FROM_NAME} <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(RESEND_API_URL, headers=self.headers, json=payload)
            if response.status_code in (200, 201):
                logger.info("email_sent", to=to_email, subject=subject[:50])
                return True
            logger.warning(
                "email_send_failed",
                to=to_email,
                status=response.status_code,
                body=response.text[:200],
            )
            return False
        except Exception as exc:
            logger.error("email_send_error", to=to_email, error=str(exc))
            return False


email_service = EmailService()


# ---------------------------------------------------------------------------
# Module-level convenience functions (used by auth_service)
# ---------------------------------------------------------------------------

async def send_password_reset_email(email: str, reset_token: str) -> None:
    """Module-level wrapper used by auth_service."""
    await email_service.send_password_reset_email(
        to_email=email,
        full_name="",
        reset_token=reset_token,
    )
