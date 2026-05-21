"""GST Notice Reply Drafting Service.

LEGAL SAFEGUARDS:
- All generated drafts include non-removable disclaimer
- Citations validated against provided legal context only
- Never hallucinate section numbers or case citations
- Human-in-loop: CA credential required before download
"""
import re
from typing import Optional

import anthropic
import openai
import pdfplumber

from app.core.config import settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

NOTICE_TYPES: dict[str, str] = {
    "DRC-01": "Show Cause Notice for Demand of Tax",
    "DRC-01A": "Intimation of Tax Ascertained",
    "DRC-01C": "Intimation of Difference in ITC",
    "DRC-07": "Summary of the Order",
    "DRC-10": "Notice for Auction of Goods",
    "ASMT-10": "Notice for Scrutiny of Returns",
    "ASMT-11": "Reply to Notice for Scrutiny",
    "REG-03": "Notice for Seeking Additional Information",
    "REG-17": "Notice to Show Cause for Cancellation",
}

LEGAL_DISCLAIMER = (
    "IMPORTANT LEGAL NOTICE: This document is a machine-generated draft prepared for "
    "informational purposes using statutory databases and user-provided inputs. It does "
    "NOT constitute formal legal representation, tax advice, or professional advocacy "
    "under Section 116 of the CGST Act, 2017, or the Advocates Act, 1961. The user, "
    "being either the registered taxpayer or their authorized representative (Chartered "
    "Accountant, Advocate, or GST Practitioner), assumes SOLE PROFESSIONAL LIABILITY for "
    "verifying the factual accuracy, legal citations, and applicability of this draft "
    "before final submission to any statutory authority. GSTSense is a technology tool "
    "and does not practice law or chartered accountancy."
)

SYSTEM_PROMPT = (
    "You are an expert GST compliance assistant helping Indian Chartered Accountants "
    "draft responses to GST notices.\n\n"
    "CRITICAL RULES you must follow without exception:\n"
    "1. Use ONLY the legal context provided to you. Never cite any case law, section, "
    "or circular that is not in the provided context.\n"
    "2. If a legal point is not supported by the provided context, write: "
    "[Legal basis not available in provided context - CA to verify]\n"
    "3. Never fabricate case citations, section numbers, or CBIC circulars.\n"
    "4. Structure every reply formally with these sections:\n"
    "   - Reference and Date\n"
    "   - Subject line\n"
    "   - Brief Facts\n"
    "   - Reply to Department Allegations\n"
    "   - Legal Grounds (only from provided context)\n"
    "   - Supporting Documents List\n"
    "   - Prayer/Request\n"
    "5. Write in formal legal English appropriate for government correspondence.\n"
    "6. Always address the reply to the designated GST officer.\n"
    "7. Include blank lines for CA/taxpayer to fill in specific details."
)

_GSTIN_PATTERN = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Z][0-9A-Z]\b")
_NOTICE_NUM_PATTERN = re.compile(
    r"(?:Notice No\.?|Reference No\.?|ARN\s*)[:\-\s]+\s*([A-Z0-9\-/]+)", re.IGNORECASE
)
_DEMAND_PATTERN = re.compile(
    r"(?:Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE
)
_PERIOD_PATTERN = re.compile(
    r"\b(20\d{2}[-–]\d{2,4}|(?:April|May|June|July|August|September|October|November|"
    r"December|January|February|March)\s+20\d{2}(?:\s+to\s+(?:March|April|May|June|July|"
    r"August|September|October|November|December|January|February)\s+20\d{2})?)\b",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{1,2}\s+(?:January|February|March|April|"
    r"May|June|July|August|September|October|November|December)\s+\d{4})\b",
    re.IGNORECASE,
)
_SECTION_PATTERN = re.compile(r"[Ss]ection\s+(\d+[A-Z]?)\s+of\s+(?:the\s+)?CGST\s+Act")
_RULE_PATTERN = re.compile(r"[Rr]ule\s+(\d+[A-Z]?)\s+of\s+(?:the\s+)?CGST\s+Rules")
_CIRCULAR_PATTERN = re.compile(r"[Cc]ircular\s+[Nn]o\.?\s*([\d/\-]+)")
_CASE_LAW_PATTERN = re.compile(
    r"(?:[A-Z][a-z]+ (?:vs?\.?|versus) [A-Z][a-z]+|"
    r"\d{4}\s+\(\d+\)\s+[A-Z]+ \d+|"
    r"AIR \d{4}|SCC \d{4})"
)


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from GST notice PDF using pdfplumber with OCR fallback."""
    text_parts: list[str] = []

    try:
        import io as _io
        with pdfplumber.open(_io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
    except Exception as exc:
        logger.warning("pdfplumber_extraction_failed", error=str(exc))

    combined = "\n".join(text_parts).strip()

    if len(combined) >= 100:
        logger.info("pdf_text_extracted_digital", chars=len(combined))
        return combined

    # Fall back to OCR for scanned PDFs
    logger.info("pdf_text_short_attempting_ocr", chars=len(combined))
    try:
        from pdf2image import convert_from_bytes
        import pytesseract

        images = convert_from_bytes(file_bytes, dpi=200)
        ocr_parts: list[str] = []
        for i, img in enumerate(images):
            page_text = pytesseract.image_to_string(img, lang="eng")
            ocr_parts.append(page_text)
            logger.debug("ocr_page_done", page=i + 1, chars=len(page_text))

        ocr_text = "\n--- Page Break ---\n".join(ocr_parts).strip()
        if ocr_text:
            logger.info("ocr_extraction_complete", chars=len(ocr_text))
            return ocr_text
    except Exception as exc:
        logger.error("ocr_extraction_failed", error=str(exc))

    if combined:
        return combined

    raise ValidationError(
        message="Could not extract readable text from the uploaded PDF. "
                "Please ensure the file is a valid GST notice document.",
        code="VAL_003",
    )


# ---------------------------------------------------------------------------
# Notice parsing
# ---------------------------------------------------------------------------


def parse_notice_details(extracted_text: str) -> dict:
    """Extract structured fields from raw notice text."""
    details: dict = {
        "notice_number": None,
        "notice_type": None,
        "taxpayer_gstin": None,
        "demand_amount": None,
        "tax_period": None,
        "response_due_date": None,
        "issuing_officer": None,
        "section_cited": None,
        "rule_cited": None,
    }

    # Notice number
    num_match = _NOTICE_NUM_PATTERN.search(extracted_text)
    if num_match:
        details["notice_number"] = num_match.group(1).strip()

    # Notice type — longest match first to avoid "DRC-01" matching before "DRC-01C"
    for code in sorted(NOTICE_TYPES.keys(), key=len, reverse=True):
        if code in extracted_text or code.replace("-", "") in extracted_text.upper():
            details["notice_type"] = code
            break

    # GSTIN (first occurrence)
    gstin_matches = _GSTIN_PATTERN.findall(extracted_text)
    if gstin_matches:
        details["taxpayer_gstin"] = gstin_matches[0]

    # Demand amount — largest rupee figure found
    demand_matches = _DEMAND_PATTERN.findall(extracted_text)
    if demand_matches:
        amounts = [float(a.replace(",", "")) for a in demand_matches]
        details["demand_amount"] = max(amounts)

    # Tax period
    period_match = _PERIOD_PATTERN.search(extracted_text)
    if period_match:
        details["tax_period"] = period_match.group(1).strip()

    # Response due date — date appearing near "reply", "response", "due"
    due_keywords = ["reply", "response", "due date", "within", "furnish"]
    for kw in due_keywords:
        kw_pos = extracted_text.lower().find(kw)
        if kw_pos >= 0:
            snippet = extracted_text[kw_pos: kw_pos + 120]
            date_m = _DATE_PATTERN.search(snippet)
            if date_m:
                details["response_due_date"] = date_m.group(1)
                break

    # Issuing officer — text after "issued by" / "signed by"
    officer_match = re.search(
        r"(?:issued by|signed by|proper officer)[:\s]+([A-Z][A-Za-z\s,]{4,60})",
        extracted_text,
        re.IGNORECASE,
    )
    if officer_match:
        details["issuing_officer"] = officer_match.group(1).strip()

    # Sections and rules
    section_matches = _SECTION_PATTERN.findall(extracted_text)
    if section_matches:
        details["section_cited"] = ", ".join(f"Section {s}" for s in section_matches[:3])

    rule_matches = _RULE_PATTERN.findall(extracted_text)
    if rule_matches:
        details["rule_cited"] = ", ".join(f"Rule {r}" for r in rule_matches[:3])

    logger.info(
        "notice_details_parsed",
        notice_type=details["notice_type"],
        notice_number=details["notice_number"],
        demand_amount=details["demand_amount"],
        has_gstin=bool(details["taxpayer_gstin"]),
    )
    return details


# ---------------------------------------------------------------------------
# Legal knowledge base
# ---------------------------------------------------------------------------


def get_relevant_legal_context(
    notice_details: dict,
    notice_text: str,
) -> str:
    """Return relevant Indian GST statutory provisions for the notice type."""
    notice_type = (notice_details.get("notice_type") or "").upper().replace("-", "_")
    contexts: list[str] = []

    if "DRC_01C" in notice_type or "DRC-01C" in notice_text.upper():
        contexts.append(_CONTEXT_DRC_01C)

    if "DRC_01" in notice_type and "DRC_01C" not in notice_type:
        contexts.append(_CONTEXT_DRC_01)

    if "ASMT_10" in notice_type:
        contexts.append(_CONTEXT_ASMT_10)

    if "REG_03" in notice_type:
        contexts.append(_CONTEXT_REG_03)

    if "REG_17" in notice_type:
        contexts.append(_CONTEXT_REG_17)

    if not contexts:
        contexts.append(_CONTEXT_GENERIC)

    contexts.append(_CONTEXT_NATURAL_JUSTICE)
    return "\n\n".join(contexts)


_CONTEXT_DRC_01C = """
=== LEGAL CONTEXT: DRC-01C (ITC Difference Notice) ===

RULE 88D — CGST Rules, 2017:
Rule 88D prescribes the procedure for intimation of differences in ITC available
in GSTR-2B and ITC availed in GSTR-3B. Where the ITC availed by a registered person
in FORM GSTR-3B for a tax period exceeds the ITC available to such person in FORM
GSTR-2B for the said tax period, the proper officer shall issue an intimation in
FORM GST DRC-01C requiring the registered person to either pay the excess ITC along
with interest or furnish a reply explaining the difference.

SECTION 16 — CGST Act, 2017 (Conditions for ITC):
Section 16(2) lays down conditions for availing ITC:
(a) The registered person is in possession of a tax invoice or debit note;
(b) The registered person has received the goods or services;
(c) The tax charged has been actually paid to the Government by the supplier;
(d) The registered person has furnished the return under Section 39.
Section 16(4) provides that ITC in respect of any supply can be availed only up to
the due date of filing of GSTR-3B for September of the following financial year or
the actual date of filing of annual return, whichever is earlier.

CIRCULAR 183/15/2022-GST:
CBIC Circular No. 183/15/2022-GST dated 27.12.2022 clarifies that in cases where
the taxpayer has availed ITC in excess of what is available in GSTR-2B, the taxpayer
may furnish a reply explaining the difference. The following are recognized grounds
for defense:
1. Supplier has filed GSTR-1 but GSTR-2B was not auto-populated due to technical
   error — taxpayer should provide invoice details and supplier filing confirmation.
2. ITC was availed in respect of invoices not reflected in GSTR-2B for the period
   but reflected in a subsequent period — reversal and re-availing permissible.
3. ITC claimed relates to goods or services genuinely received and tax paid by supplier.

DEFENSE GROUNDS WHERE SUPPLIER HAS FILED:
Where the supplier has actually filed GSTR-1/IFF and paid the tax but the same has
not been reflected in GSTR-2B, the taxpayer can defend by:
- Submitting supplier's GSTR-1 acknowledgment
- Submitting supplier's tax payment challan (CPIN)
- Invoices matching the ITC claimed
- Proof of receipt of goods/services

DEFENSE GROUNDS FOR BONA FIDE TRANSACTIONS:
For genuine business transactions where the supplier has defaulted in filing:
- Section 16(2)(c) imposes liability on the supplier, not the recipient, for tax payment
- The recipient acted in good faith based on the invoice
- Rule 88D allows the taxpayer to respond with explanation within the time period allowed
"""

_CONTEXT_DRC_01 = """
=== LEGAL CONTEXT: DRC-01 (Show Cause Notice / Demand) ===

SECTION 73 — CGST Act, 2017 (Cases not involving fraud):
Section 73 provides for determination of tax not paid or short paid or erroneously
refunded or ITC wrongly availed or utilized for any reason other than fraud or any
willful misstatement or suppression of facts. The proper officer shall issue a notice
requiring the person to show cause as to why the tax, interest, and penalty should not
be demanded. Section 73(5) provides that if the person pays the tax demanded along with
interest before issuance of SCN, the penalty shall be 10% of tax or ₹10,000 whichever
is higher. Section 73(8) provides that if the demand is paid before the order, penalty
shall be 10% of tax demanded.

SECTION 74 — CGST Act, 2017 (Fraud cases):
Section 74 applies where tax has not been paid or short paid or erroneously refunded or
ITC wrongly availed or utilized by reason of fraud or any willful misstatement or
suppression of facts. The maximum penalty under Section 74 is 100% of the tax amount.

TIME LIMITS FOR DEMAND:
Under Section 73, the SCN must be issued at least 3 months before the time limit for
adjudication. The adjudication order must be passed within 3 years from the due date
of annual return for the relevant year. Under Section 74, the SCN must be issued at
least 6 months before the adjudication time limit of 5 years.

REDUCED PENALTY — SECTION 73(5) AND 73(8):
If the taxable person pays the tax and interest before issuance of notice under Section
73(1), no SCN shall be issued. If payment is made after notice but before adjudication
order, penalty is reduced to 10% of tax.
"""

_CONTEXT_ASMT_10 = """
=== LEGAL CONTEXT: ASMT-10 (Scrutiny Notice) ===

SECTION 61 — CGST Act, 2017:
Section 61 empowers the proper officer to scrutinize the returns filed by a registered
person and related particulars to verify the correctness of the return. Where any
discrepancies are noticed, the proper officer shall inform the registered person and
seek explanation. The registered person shall, within 30 days of receipt of intimation
(or such extended period as may be permitted), provide explanation or rectify the
discrepancy in the return to be filed for the month in which such discrepancy is noticed.

SCOPE OF SCRUTINY:
The proper officer under Section 61 can only scrutinize returns and related particulars.
The scrutiny is limited to:
1. Arithmetical errors in the return
2. Discrepancies between different returns filed by the taxpayer
3. Discrepancies between returns filed and the tax actually paid
The proper officer cannot reassess taxable value or question business decisions
without following the procedure under Section 73 or 74.

RIGHTS OF TAXPAYER IN SCRUTINY:
1. Right to receive clear notice specifying the discrepancy
2. Right to 30 days to respond (extendable on request)
3. Right to submit documentary evidence in support of reply
4. No adverse inference shall be drawn without opportunity of hearing
5. If explanation is satisfactory, no further action shall be taken
"""

_CONTEXT_REG_03 = """
=== LEGAL CONTEXT: REG-03 (Registration Clarification Notice) ===

SECTION 25 — CGST Act, 2017:
Section 25 governs the registration process. Every person liable to be registered
must apply for registration within 30 days from the date of becoming liable.
The proper officer has powers to seek additional information before granting registration.

RULE 9 — CGST Rules, 2017:
Rule 9 provides that the proper officer shall examine the application and the
accompanying documents, and if found in order, approve the application. If additional
clarification is required, the proper officer shall issue notice in FORM GST REG-03
within 3 working days of receipt of application. The applicant shall furnish clarification
in FORM GST REG-04 within 7 working days.

ACCEPTABLE ADDRESS PROOF DOCUMENTS:
1. Electricity bill (not more than 2 months old)
2. Rent/lease agreement with No Objection Certificate (NOC)
3. Municipal khata copy
4. Property tax receipt
5. Legal ownership document (sale deed, khata certificate)
6. Any government issued document showing the premises address
"""

_CONTEXT_REG_17 = """
=== LEGAL CONTEXT: REG-17 (Cancellation Notice) ===

SECTION 29 — CGST Act, 2017:
Section 29 provides for cancellation or suspension of registration. The proper officer
may cancel registration where:
(a) The business has been discontinued or transferred
(b) The taxable person ceases to be liable to pay tax
(c) Registration was obtained by fraud, willful misstatement, or suppression of facts
(d) The registered person has contravened provisions of the Act

GROUNDS FOR OPPOSING CANCELLATION:
1. Business is ongoing and registration is required
2. All returns have been filed and dues are paid
3. Voluntary compliance: any outstanding returns or taxes can be paid immediately
4. The grounds cited for cancellation are factually incorrect
5. The proper officer has not followed the principles of natural justice

DEFENSE — VOLUNTARY COMPLIANCE:
Where cancellation is proposed due to non-filing of returns, the registered person can:
1. File all pending returns immediately before or during the reply period
2. Demonstrate continuous business activity with invoice records
3. Show that non-filing was due to technical difficulties on the portal
"""

_CONTEXT_GENERIC = """
=== GENERAL GST PROVISIONS ===

SECTION 75 — CGST Act, 2017 (General provisions relating to determination):
Section 75 provides general procedural safeguards. The proper officer shall issue
a speaking order, consider the material on record, and give adequate opportunity of
hearing before passing any adverse order.

SECTION 67(10) — CGST Act, 2017:
Every search, seizure, and inspection must follow due process. Any statement obtained
during inspection is not conclusive evidence.
"""

_CONTEXT_NATURAL_JUSTICE = """
=== PRINCIPLES OF NATURAL JUSTICE ===

AUDI ALTERAM PARTEM (Right to be heard):
No adverse order shall be passed against a person without giving them a reasonable
opportunity to present their case. This principle is embedded in Section 75(4) of the
CGST Act which mandates a personal hearing before an adverse order is passed.

RIGHT TO KNOW CHARGES:
The registered person is entitled to receive a clear and specific notice setting out
the exact nature of the discrepancy or allegation. A vague or ambiguous notice does
not satisfy the requirements of natural justice.

PRINCIPLE OF REASONABLENESS:
Administrative authorities must act fairly and reasonably. Any order passed without
application of mind or based on irrelevant considerations is liable to be set aside.

OPPORTUNITY FOR COMPLIANCE:
Where a registered person has made a bona fide error, the department should consider
the possibility of voluntary compliance rather than punitive action, especially for
first-time or technical defaults.
"""


# ---------------------------------------------------------------------------
# Draft generation
# ---------------------------------------------------------------------------


async def draft_notice_reply(
    notice_text: str,
    notice_details: dict,
    organization_name: str,
    gstin: str,
    additional_context: Optional[str] = None,
) -> str:
    """Generate AI-powered notice reply draft using Claude → GPT-4o → template."""
    legal_context = get_relevant_legal_context(notice_details, notice_text)

    notice_type = notice_details.get("notice_type") or "GST Notice"
    notice_number = notice_details.get("notice_number") or "[Notice Number]"
    demand_amount = notice_details.get("demand_amount")
    tax_period = notice_details.get("tax_period") or "[Tax Period]"

    demand_str = f"₹{demand_amount:,.2f}" if demand_amount else "[Amount as per notice]"

    prompt = (
        f"Draft a formal GST notice reply for the following:\n\n"
        f"TAXPAYER DETAILS:\n"
        f"Organization Name: {organization_name}\n"
        f"GSTIN: {gstin}\n\n"
        f"NOTICE DETAILS:\n"
        f"Notice Type: {notice_type} — {NOTICE_TYPES.get(notice_type, 'GST Notice')}\n"
        f"Notice Number: {notice_number}\n"
        f"Tax Period: {tax_period}\n"
        f"Demand Amount: {demand_str}\n\n"
        f"NOTICE TEXT (extracted from PDF):\n"
        f"{notice_text[:3000]}\n\n"
    )

    if additional_context:
        prompt += f"ADDITIONAL CONTEXT FROM TAXPAYER:\n{additional_context[:500]}\n\n"

    prompt += (
        f"LEGAL PROVISIONS (use ONLY these):\n{legal_context}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Draft a complete formal reply in 7 sections as instructed\n"
        f"2. Use ONLY the legal provisions provided above\n"
        f"3. Mark unclear facts as [PLACEHOLDER - CA to verify]\n"
        f"4. Include a supporting documents checklist at the end\n"
        f"5. Address the reply to the proper officer\n"
        f"6. Never cite anything not in the legal context above\n"
    )

    try:
        draft = await _call_claude_for_draft(prompt, legal_context)
        logger.info("notice_draft_generated_by_claude", notice_number=notice_number)
        return draft
    except Exception as exc:
        logger.warning("claude_draft_failed", error=str(exc))

    try:
        draft = await _call_openai_for_draft(prompt, legal_context)
        logger.info("notice_draft_generated_by_openai", notice_number=notice_number)
        return draft
    except Exception as exc:
        logger.warning("openai_draft_failed", error=str(exc))

    logger.info("notice_draft_using_template", notice_number=notice_number)
    return get_template_draft(notice_details, organization_name, gstin)


async def _call_claude_for_draft(prompt: str, legal_context: str) -> str:
    """Call Claude Sonnet to generate notice reply draft."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=settings.AI_MAX_TOKENS,
        temperature=settings.AI_TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    block = response.content[0]
    text = block.text.strip() if hasattr(block, "text") else ""
    if not text:
        raise ExternalServiceError.ai_service_unavailable()
    return text


async def _call_openai_for_draft(prompt: str, legal_context: str) -> str:
    """Fallback to GPT-4o if Claude fails."""
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4o",
        max_tokens=settings.AI_MAX_TOKENS,
        temperature=settings.AI_TEMPERATURE,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise ExternalServiceError.ai_service_unavailable()
    return text


def get_template_draft(
    notice_details: dict,
    organization_name: str,
    gstin: str,
) -> str:
    """Last-resort template draft when both AI services fail. Always succeeds."""
    notice_type = notice_details.get("notice_type") or "GST Notice"
    notice_number = notice_details.get("notice_number") or "[Notice Number]"
    tax_period = notice_details.get("tax_period") or "[Tax Period]"
    demand_amount = notice_details.get("demand_amount")
    demand_str = f"₹{demand_amount:,.2f}" if demand_amount else "[Amount as per notice]"
    type_desc = NOTICE_TYPES.get(notice_type, "GST Notice")

    return f"""
Reference: [Your Reference Number]
Date: [Date]

To,
The Proper Officer,
[GST Ward/Circle/Division],
[Jurisdiction Address]

Subject: Reply to {notice_type} — {type_desc} — Notice No. {notice_number} for the period {tax_period}

Sir/Madam,

1. REFERENCE AND BRIEF FACTS:
We, {organization_name} (GSTIN: {gstin}), are in receipt of the above-referenced
notice dated [Notice Date] issued by your good office. The notice pertains to the
tax period {tax_period} and raises a demand/query of {demand_str}.

We humbly submit this reply in accordance with the time allowed under the said notice.

2. REPLY TO DEPARTMENT ALLEGATIONS:
[PLACEHOLDER - CA to verify facts and fill in specific reply to each allegation
raised in the notice. Provide specific documentary evidence for each point.]

The alleged discrepancy/demand, if any, arises due to [PLACEHOLDER - reason to be
stated by taxpayer/CA based on actual facts of the case].

3. LEGAL GROUNDS:
[PLACEHOLDER - CA to verify and insert applicable legal provisions from CGST Act
2017 and CGST Rules 2017 that support the taxpayer's position.
Reference only sections and rules actually cited in the legal context provided.]

[Legal basis not available in provided context - CA to verify and insert applicable
sections of CGST Act, 2017, relevant CBIC circulars, and notifications.]

4. SUPPORTING DOCUMENTS:
We enclose/rely upon the following documents in support of our reply:
a. Copies of relevant invoices: [PLACEHOLDER - list invoice numbers]
b. GSTR-1 filing acknowledgment for the relevant period
c. GSTR-3B filing acknowledgment for the relevant period
d. GSTR-2B auto-drafted statement for the relevant period
e. Bank statements evidencing payments to suppliers
f. [PLACEHOLDER - any other relevant documents]

5. PRAYER/REQUEST:
In view of the above facts, submissions, and documents, we most respectfully pray that:
a. The notice/demand may kindly be dropped in its entirety; OR
b. The matter may be adjudicated after considering our reply and documents; AND
c. An opportunity of personal hearing may be granted before passing any adverse order,
   as required under Section 75(4) of the CGST Act, 2017.

We assure your good office of our full cooperation and commitment to GST compliance.

Thanking you,

Yours faithfully,

Signature: _________________________
Name: [PLACEHOLDER - Authorized Signatory Name]
Designation: [PLACEHOLDER - Designation]
GSTIN: {gstin}
Date: [Date]

[If signed by CA/Advocate/GST Practitioner:]
ICAI/Bar Council/GST Practitioner No.: _________________________
"""


# ---------------------------------------------------------------------------
# Citation validation
# ---------------------------------------------------------------------------


def validate_draft_citations(
    draft_text: str,
    legal_context: str,
) -> tuple[str, list[str]]:
    """Validate all legal citations in draft exist in provided legal context.

    Scans draft for Section/Rule/Circular/case law citations.
    Any citation not found in legal_context is replaced with a CA-verification marker.
    Returns (cleaned_draft, warnings_list).
    """
    warnings: list[str] = []
    cleaned = draft_text

    # Check section citations
    for match in _SECTION_PATTERN.finditer(draft_text):
        full_match = match.group(0)
        if full_match not in legal_context:
            replacement = "[Citation requires CA verification]"
            cleaned = cleaned.replace(full_match, replacement, 1)
            warning = f"Unverified citation replaced: '{full_match}'"
            warnings.append(warning)
            logger.warning("hallucinated_section_replaced", citation=full_match)

    # Check rule citations
    for match in _RULE_PATTERN.finditer(draft_text):
        full_match = match.group(0)
        if full_match not in legal_context:
            replacement = "[Citation requires CA verification]"
            cleaned = cleaned.replace(full_match, replacement, 1)
            warning = f"Unverified citation replaced: '{full_match}'"
            warnings.append(warning)
            logger.warning("hallucinated_rule_replaced", citation=full_match)

    # Check circular citations
    for match in _CIRCULAR_PATTERN.finditer(draft_text):
        full_match = match.group(0)
        if full_match not in legal_context:
            replacement = "[Citation requires CA verification]"
            cleaned = cleaned.replace(full_match, replacement, 1)
            warning = f"Unverified circular citation replaced: '{full_match}'"
            warnings.append(warning)
            logger.warning("hallucinated_circular_replaced", citation=full_match)

    # Check case law citations — these are especially dangerous to hallucinate
    for match in _CASE_LAW_PATTERN.finditer(draft_text):
        full_match = match.group(0)
        if full_match not in legal_context:
            replacement = "[Case citation requires CA verification — do not use without confirmation]"
            cleaned = cleaned.replace(full_match, replacement, 1)
            warning = f"Unverified case law citation removed: '{full_match}'"
            warnings.append(warning)
            logger.warning("hallucinated_case_law_removed", citation=full_match)

    if warnings:
        logger.info("citation_validation_complete", replaced_count=len(warnings))
    else:
        logger.info("citation_validation_clean")

    return cleaned, warnings
