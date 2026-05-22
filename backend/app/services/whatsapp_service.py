from decimal import Decimal

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

INTERAKT_API_URL = "https://api.interakt.ai/v1/public/message/"

GST_DEADLINES = {
    "GSTR1": 11,
    "GSTR3B": 20,
}


class WhatsAppService:
    def __init__(self) -> None:
        self.api_key = settings.INTERAKT_API_KEY
        self.headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_scan_complete_notification(
        self,
        phone: str,
        business_name: str,
        scan_month: str,
        total_mismatches: int,
        total_rupee_risk: Decimal,
        scan_id: str,
    ) -> bool:
        """Send WhatsApp message when scan completes. Never raises."""
        try:
            from datetime import datetime
            try:
                dt = datetime.strptime(scan_month, "%Y-%m")
                month_label = dt.strftime("%B %Y")
            except ValueError:
                month_label = scan_month

            # Format rupee risk in Indian style
            amount_str = f"₹{total_rupee_risk:,.2f}"

            message = (
                f"Hi {business_name},\n\n"
                f"Your GSTSense scan for {month_label} is complete.\n\n"
                f"📊 Results:\n"
                f"• Mismatches found: {total_mismatches}\n"
                f"• Total rupee risk: {amount_str}\n\n"
                f"View your full report: https://gstsense.in/scan/report/{scan_id}\n\n"
                f"— GSTSense Team"
            )
            return await self._send_message(phone, message)
        except Exception as exc:
            logger.error("whatsapp_scan_complete_error", scan_id=scan_id, error=str(exc))
            return False

    async def send_deadline_reminder(
        self,
        phone: str,
        business_name: str,
        filing_type: str,
        due_date: str,
        days_remaining: int,
    ) -> bool:
        """Send GST deadline reminder. Never raises."""
        try:
            message = (
                f"Hi {business_name},\n\n"
                f"⏰ Reminder: {filing_type} is due on {due_date} "
                f"({days_remaining} days remaining).\n\n"
                f"Run a free mismatch check before filing: https://gstsense.in/scan\n\n"
                f"— GSTSense Team"
            )
            return await self._send_message(phone, message)
        except Exception as exc:
            logger.error("whatsapp_deadline_reminder_error", filing_type=filing_type, error=str(exc))
            return False

    async def _send_message(self, phone: str, message: str) -> bool:
        """Send WhatsApp message via Interakt API. Returns True on success."""
        # Normalise phone: ensure 91 prefix, strip spaces/dashes
        phone = phone.strip().replace(" ", "").replace("-", "")
        if not phone.startswith("91"):
            phone = "91" + phone.lstrip("+")

        payload = {
            "countryCode": "+91",
            "phoneNumber": phone[2:],  # Interakt expects number without country code
            "callbackData": "gstsense_notification",
            "type": "Text",
            "data": {
                "message": message,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    INTERAKT_API_URL,
                    headers=self.headers,
                    json=payload,
                )
            if response.status_code in (200, 201):
                logger.info("whatsapp_sent", phone=phone[-4:])
                return True
            logger.warning(
                "whatsapp_send_failed",
                phone=phone[-4:],
                status=response.status_code,
                body=response.text[:200],
            )
            return False
        except Exception as exc:
            logger.error("whatsapp_send_error", phone=phone[-4:], error=str(exc))
            return False


whatsapp_service = WhatsAppService()
