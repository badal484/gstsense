import json
from typing import Optional

import anthropic
import openai

from app.core.config import settings
from app.core.logging import get_logger
from app.models.mismatch import MismatchType
from app.services.reconciler import MismatchDetail

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a GST compliance expert helping Indian small business owners understand their tax filing errors.

Your explanations must:
- Be in simple plain English that a non-accountant understands
- Mention the specific rule violated (Rule 88C for GSTR-1/3B mismatch)
- Include the rupee amount at risk
- Give one specific corrective action
- Be exactly 2-3 sentences
- Never use legal jargon or complex tax terminology
- Be written for an Indian business owner

Always respond with valid JSON only. No other text."""

EXPLANATION_TEMPLATES = {
    MismatchType.missing_in_3b: (
        "Invoice {invoice_number} from supplier {gstin} is declared in your GSTR-1 sales returns "
        "but is missing from your GSTR-3B summary return. "
        "This ₹{amount} discrepancy may trigger a Rule 88C notice from the GST department. "
        "Please add this invoice to your next GSTR-3B filing or file a GSTR-1A amendment to correct it."
    ),
    MismatchType.missing_in_1: (
        "Invoice {invoice_number} from supplier {gstin} appears in your GSTR-3B but has no matching "
        "entry in your GSTR-1. "
        "This ₹{amount} gap may attract scrutiny under Rule 88C. "
        "Check if this invoice was accidentally omitted from your GSTR-1 and file an amendment if needed."
    ),
    MismatchType.value_mismatch: (
        "The taxable value for invoice {invoice_number} from supplier {gstin} differs by ₹{amount} "
        "between your GSTR-1 and GSTR-3B returns. "
        "This mismatch can trigger an automated Rule 88C notice demanding explanation. "
        "Review both returns and file a GSTR-1A amendment to make the values match."
    ),
    MismatchType.tax_mismatch: (
        "The tax amount for invoice {invoice_number} from supplier {gstin} differs by ₹{amount} "
        "between your GSTR-1 and GSTR-3B. "
        "Even small tax amount differences trigger Rule 88C automated notices. "
        "Verify the correct tax rate and file a correction before your next filing deadline."
    ),
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def explain_mismatches(
    mismatches: list[MismatchDetail],
    scan_month: str,
) -> list[MismatchDetail]:
    """Populate ai_explanation on every MismatchDetail.

    Strategy: Claude Sonnet → GPT-4o → templates. Never blocks scan delivery.
    """
    if not mismatches:
        return mismatches

    try:
        return await _explain_with_claude(mismatches, scan_month)
    except Exception as exc:
        logger.warning("claude_explain_failed", error=str(exc))

    try:
        return await _explain_with_openai(mismatches, scan_month)
    except Exception as exc:
        logger.warning("openai_explain_failed", error=str(exc))

    logger.info("ai_explain_using_templates", count=len(mismatches))
    return _apply_templates(mismatches)


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------


async def _explain_with_claude(
    mismatches: list[MismatchDetail],
    scan_month: str,
) -> list[MismatchDetail]:
    """Send all mismatches to Claude Sonnet in one batch call."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    payload = {
        "scan_month": scan_month,
        "mismatches": [
            {
                "invoice_number": m.invoice_number,
                "supplier_gstin": m.supplier_gstin,
                "mismatch_type": m.mismatch_type.value,
                "rupee_difference": str(m.rupee_difference),
                "gstr1_value": str(m.gstr1_taxable_value),
                "gstr3b_value": str(m.gstr3b_taxable_value),
            }
            for m in mismatches
        ],
    }

    user_message = (
        f"Explain these GST mismatches for scan month {scan_month}. "
        f"Respond with a JSON array where each item has "
        f'"invoice_number" and "explanation" fields.\n\n'
        f"{json.dumps(payload)}"
    )

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=settings.AI_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    block = response.content[0]
    raw = block.text.strip() if hasattr(block, "text") else ""
    return _merge_explanations(mismatches, raw, "claude")


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


async def _explain_with_openai(
    mismatches: list[MismatchDetail],
    scan_month: str,
) -> list[MismatchDetail]:
    """Fallback: send all mismatches to GPT-4o in one batch call."""
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    payload = {
        "scan_month": scan_month,
        "mismatches": [
            {
                "invoice_number": m.invoice_number,
                "supplier_gstin": m.supplier_gstin,
                "mismatch_type": m.mismatch_type.value,
                "rupee_difference": str(m.rupee_difference),
                "gstr1_value": str(m.gstr1_taxable_value),
                "gstr3b_value": str(m.gstr3b_taxable_value),
            }
            for m in mismatches
        ],
    }

    user_message = (
        f"Explain these GST mismatches for scan month {scan_month}. "
        f"Respond with a JSON array where each item has "
        f'"invoice_number" and "explanation" fields.\n\n'
        f"{json.dumps(payload)}"
    )

    response = await client.chat.completions.create(
        model="gpt-4o",
        max_tokens=settings.AI_MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    raw = (response.choices[0].message.content or "").strip()
    return _merge_explanations(mismatches, raw, "openai")


# ---------------------------------------------------------------------------
# Template fallback
# ---------------------------------------------------------------------------


def _apply_templates(mismatches: list[MismatchDetail]) -> list[MismatchDetail]:
    """Generate rule-based explanations — never raises."""
    for m in mismatches:
        template = EXPLANATION_TEMPLATES.get(m.mismatch_type, "")
        m.ai_explanation = template.format(
            invoice_number=m.invoice_number,
            gstin=m.supplier_gstin,
            amount=f"{m.rupee_difference:,.2f}",
        )
    return mismatches


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _merge_explanations(
    mismatches: list[MismatchDetail],
    raw_response: str,
    source: str,
) -> list[MismatchDetail]:
    """Parse JSON response and attach explanations to the matching mismatches."""
    try:
        # Strip markdown fences if present
        text = raw_response
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text.strip())
        if not isinstance(parsed, list):
            raise ValueError("Expected JSON array")

        index: dict[str, str] = {
            item["invoice_number"]: item["explanation"]
            for item in parsed
            if isinstance(item, dict) and "invoice_number" in item and "explanation" in item
        }
        for m in mismatches:
            explanation = index.get(m.invoice_number)
            if explanation:
                m.ai_explanation = explanation
                logger.debug(
                    "ai_explanation_attached",
                    source=source,
                    invoice_number=m.invoice_number,
                )

        logger.info(
            "ai_explanations_merged",
            source=source,
            total=len(mismatches),
            matched=sum(1 for m in mismatches if m.ai_explanation),
        )
    except Exception as exc:
        logger.warning(
            "ai_response_parse_failed",
            source=source,
            error=str(exc),
            raw_preview=raw_response[:200],
        )
        return _apply_templates(mismatches)

    return mismatches
