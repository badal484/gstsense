import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

import pandas as pd

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.services.parser import (
    find_header_row,
    normalize_amount,
    normalize_date,
    normalize_gstin,
    normalize_invoice_number,
    validate_excel_bytes,
)

logger = get_logger(__name__)

AMOUNT_TOLERANCE = Decimal("1.00")


class ITCIssueType(str, Enum):
    UNCLAIMED = "unclaimed"
    EXCESS_CLAIMED = "excess_claimed"
    SUPPLIER_NOT_FILED = "supplier_not_filed"
    RATE_DIFFERENCE = "rate_difference"


@dataclass
class ITCIssue:
    supplier_gstin: str
    supplier_name: Optional[str]
    invoice_number: str
    invoice_date: Optional[str]
    issue_type: ITCIssueType
    available_itc: Decimal
    claimed_itc: Decimal
    difference: Decimal
    recommendation: str


@dataclass
class ITCAnalysisResult:
    total_invoices_checked: int
    total_unique_suppliers: int
    total_unclaimed_itc: Decimal
    total_excess_claimed: Decimal
    total_at_risk: Decimal
    issues: list[ITCIssue]
    issues_by_type: dict[str, int]
    processing_time_ms: int
    warnings: list[str] = field(default_factory=list)


GSTR2B_COLUMN_VARIANTS: dict[str, list[str]] = {
    "supplier_gstin": [
        "GSTIN of Supplier",
        "Supplier GSTIN",
        "GSTIN",
        "gstin",
        "GSTIN of supplier",
    ],
    "invoice_number": [
        "Invoice Number",
        "Invoice No",
        "Invoice No.",
        "invoice_number",
        "Document Number",
    ],
    "invoice_date": [
        "Invoice Date",
        "Date",
        "invoice_date",
        "Document Date",
    ],
    "taxable_value": [
        "Taxable Value",
        "taxable_value",
        "Value",
        "Taxable Amount",
    ],
    "igst_available": [
        "Integrated Tax",
        "IGST",
        "igst_available",
        "Integrated Tax Amount",
        "IGST Amount",
    ],
    "cgst_available": [
        "Central Tax",
        "CGST",
        "cgst_available",
        "Central Tax Amount",
        "CGST Amount",
    ],
    "sgst_available": [
        "State/UT Tax",
        "SGST",
        "sgst_available",
        "State/UT Tax Amount",
        "SGST Amount",
    ],
    "itc_availability": [
        "ITC Availability",
        "itc_availability",
        "Eligibility",
        "ITC Eligible",
    ],
    "supplier_filing_status": [
        "Supplier Filing Status",
        "Filing Status",
        "supplier_filing_status",
        "GSTR-1 Filing Status",
        "Supplier Status",
    ],
}


def _resolve_columns(df: pd.DataFrame, variants: dict[str, list[str]]) -> dict[str, str]:
    """Return mapping of canonical_name -> actual_column for columns found in df."""
    col_lower = {c.lower().strip(): c for c in df.columns}
    resolved: dict[str, str] = {}
    for canonical, options in variants.items():
        for opt in options:
            if opt.lower().strip() in col_lower:
                resolved[canonical] = col_lower[opt.lower().strip()]
                break
    return resolved


def parse_gstr2b(file_bytes: bytes) -> pd.DataFrame:
    """Parse GSTR-2B Excel file and return a clean normalised DataFrame."""
    validate_excel_bytes(file_bytes)

    import io
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)

    header_row = find_header_row(raw, GSTR2B_COLUMN_VARIANTS)
    df = pd.read_excel(io.BytesIO(file_bytes), header=header_row, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    col_map = _resolve_columns(df, GSTR2B_COLUMN_VARIANTS)

    required = {"supplier_gstin", "invoice_number"}
    missing = required - set(col_map.keys())
    if missing:
        raise ValidationError(
            message=f"GSTR-2B file is missing required columns: {missing}. "
                    "Please upload a valid GSTR-2B Excel export.",
            code="VAL_003",
        )

    rows = []
    for _, row in df.iterrows():
        gstin = normalize_gstin(row.get(col_map.get("supplier_gstin", ""), None))
        inv_no = normalize_invoice_number(row.get(col_map.get("invoice_number", ""), None))
        if not gstin or not inv_no:
            continue

        igst = normalize_amount(row.get(col_map.get("igst_available", ""), None))
        cgst = normalize_amount(row.get(col_map.get("cgst_available", ""), None))
        sgst = normalize_amount(row.get(col_map.get("sgst_available", ""), None))

        itc_flag_raw = str(row.get(col_map.get("itc_availability", ""), "YES")).strip().upper()
        itc_availability = itc_flag_raw if itc_flag_raw else "YES"

        filing_raw = str(row.get(col_map.get("supplier_filing_status", ""), "Filed")).strip()
        supplier_filing_status = filing_raw if filing_raw and filing_raw != "NAN" else "Filed"

        rows.append({
            "supplier_gstin": gstin,
            "invoice_number": inv_no,
            "invoice_date": normalize_date(row.get(col_map.get("invoice_date", ""), None)),
            "taxable_value": normalize_amount(row.get(col_map.get("taxable_value", ""), None)),
            "igst_available": igst,
            "cgst_available": cgst,
            "sgst_available": sgst,
            "total_available_itc": igst + cgst + sgst,
            "itc_availability": itc_availability,
            "supplier_filing_status": supplier_filing_status,
        })

    result_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        "supplier_gstin", "invoice_number", "invoice_date", "taxable_value",
        "igst_available", "cgst_available", "sgst_available",
        "total_available_itc", "itc_availability", "supplier_filing_status",
    ])

    logger.info("gstr2b_parsed", row_count=len(result_df))
    return result_df


def _inv_key(gstin: str, inv_no: str) -> str:
    return f"{gstin}|{inv_no}"


def analyze_itc(
    gstr3b_df: pd.DataFrame,
    gstr2b_df: pd.DataFrame,
    warnings: Optional[list[str]] = None,
) -> ITCAnalysisResult:
    """Core ITC analysis: compare available ITC (GSTR-2B) vs claimed ITC (GSTR-3B)."""
    start_ms = int(time.time() * 1000)
    warn_list: list[str] = list(warnings or [])
    issues: list[ITCIssue] = []

    # ── STEP 1: Build GSTR-2B lookup ──────────────────────────────────────
    gstr2b_lookup: dict[str, dict] = {}
    if not gstr2b_df.empty:
        for _, row in gstr2b_df.iterrows():
            gstin = str(row.get("supplier_gstin", "")).strip()
            inv = str(row.get("invoice_number", "")).strip()
            if not gstin or not inv:
                continue
            key = _inv_key(gstin, inv)
            gstr2b_lookup[key] = {
                "supplier_gstin": gstin,
                "invoice_number": inv,
                "invoice_date": row.get("invoice_date"),
                "total_available_itc": Decimal(str(row.get("total_available_itc", 0))),
                "igst_available": Decimal(str(row.get("igst_available", 0))),
                "cgst_available": Decimal(str(row.get("cgst_available", 0))),
                "sgst_available": Decimal(str(row.get("sgst_available", 0))),
                "itc_availability": str(row.get("itc_availability", "YES")).strip().upper(),
                "supplier_filing_status": str(row.get("supplier_filing_status", "Filed")).strip(),
            }

    # ── STEP 2: Build GSTR-3B lookup ──────────────────────────────────────
    gstr3b_lookup: dict[str, dict] = {}
    if not gstr3b_df.empty:
        igst_col = "igst_amount" if "igst_amount" in gstr3b_df.columns else None
        cgst_col = "cgst_amount" if "cgst_amount" in gstr3b_df.columns else None
        sgst_col = "sgst_amount" if "sgst_amount" in gstr3b_df.columns else None

        for _, row in gstr3b_df.iterrows():
            gstin_val = row.get("supplier_gstin", "")
            inv_val = row.get("invoice_number", "")
            if not gstin_val or not inv_val:
                continue
            gstin = str(gstin_val).strip()
            inv = str(inv_val).strip()
            if not gstin or not inv:
                continue
            key = _inv_key(gstin, inv)

            igst = Decimal(str(row.get(igst_col, 0) if igst_col else 0))
            cgst = Decimal(str(row.get(cgst_col, 0) if cgst_col else 0))
            sgst = Decimal(str(row.get(sgst_col, 0) if sgst_col else 0))

            gstr3b_lookup[key] = {
                "supplier_gstin": gstin,
                "invoice_number": inv,
                "igst_claimed": igst,
                "cgst_claimed": cgst,
                "sgst_claimed": sgst,
                "total_claimed_itc": igst + cgst + sgst,
            }

    all_keys = set(gstr2b_lookup.keys()) | set(gstr3b_lookup.keys())
    total_invoices_checked = len(all_keys)
    all_gstins = {k.split("|")[0] for k in all_keys}

    # ── STEP 3: Find UNCLAIMED ITC ────────────────────────────────────────
    for key, g2b in gstr2b_lookup.items():
        avail_flag = g2b["itc_availability"]
        if avail_flag not in ("YES", "Y", "ELIGIBLE", "YES - IGST", "YES - CGST/SGST"):
            continue  # ineligible ITC — skip

        available = g2b["total_available_itc"]
        gstin = g2b["supplier_gstin"]
        inv = g2b["invoice_number"]
        date = g2b.get("invoice_date")

        if key not in gstr3b_lookup:
            # Fully unclaimed
            issues.append(ITCIssue(
                supplier_gstin=gstin,
                supplier_name=None,
                invoice_number=inv,
                invoice_date=date,
                issue_type=ITCIssueType.UNCLAIMED,
                available_itc=available,
                claimed_itc=Decimal("0"),
                difference=available,
                recommendation=(
                    f"Claim this ITC in your next GSTR-3B filing. "
                    f"Available credit of ₹{available:,.2f} from supplier "
                    f"{gstin} will lapse if not claimed within the time limit."
                ),
            ))
        else:
            claimed = gstr3b_lookup[key]["total_claimed_itc"]
            diff = available - claimed
            if diff > AMOUNT_TOLERANCE:
                issues.append(ITCIssue(
                    supplier_gstin=gstin,
                    supplier_name=None,
                    invoice_number=inv,
                    invoice_date=date,
                    issue_type=ITCIssueType.UNCLAIMED,
                    available_itc=available,
                    claimed_itc=claimed,
                    difference=diff,
                    recommendation=(
                        f"You claimed ₹{claimed:,.2f} but ₹{available:,.2f} is available. "
                        f"Claim the additional ₹{diff:,.2f} in your next GSTR-3B "
                        f"to avoid losing this credit."
                    ),
                ))

    # ── STEP 4: Find EXCESS_CLAIMED ───────────────────────────────────────
    for key, g3b in gstr3b_lookup.items():
        claimed = g3b["total_claimed_itc"]
        gstin = g3b["supplier_gstin"]
        inv = g3b["invoice_number"]

        if key not in gstr2b_lookup:
            issues.append(ITCIssue(
                supplier_gstin=gstin,
                supplier_name=None,
                invoice_number=inv,
                invoice_date=None,
                issue_type=ITCIssueType.EXCESS_CLAIMED,
                available_itc=Decimal("0"),
                claimed_itc=claimed,
                difference=claimed,
                recommendation=(
                    f"Your supplier has not filed their GSTR-1 for this invoice. "
                    f"The ITC of ₹{claimed:,.2f} you claimed may be disallowed under "
                    f"Rule 88D. Contact supplier {gstin} to file immediately."
                ),
            ))
        else:
            available = gstr2b_lookup[key]["total_available_itc"]
            diff = claimed - available
            if diff > AMOUNT_TOLERANCE:
                issues.append(ITCIssue(
                    supplier_gstin=gstin,
                    supplier_name=None,
                    invoice_number=inv,
                    invoice_date=gstr2b_lookup[key].get("invoice_date"),
                    issue_type=ITCIssueType.EXCESS_CLAIMED,
                    available_itc=available,
                    claimed_itc=claimed,
                    difference=diff,
                    recommendation=(
                        f"You claimed ₹{diff:,.2f} more than available. "
                        f"This excess claim of ₹{diff:,.2f} may trigger a Rule 88D notice. "
                        f"Reverse this amount in your next GSTR-3B."
                    ),
                ))

    # ── STEP 5: Find SUPPLIER_NOT_FILED ───────────────────────────────────
    for key, g2b in gstr2b_lookup.items():
        if g2b["supplier_filing_status"].lower() in ("not filed", "not_filed", "pending"):
            available = g2b["total_available_itc"]
            gstin = g2b["supplier_gstin"]
            inv = g2b["invoice_number"]
            date = g2b.get("invoice_date")

            # Only add if not already an EXCESS_CLAIMED issue for this key
            already_excess = any(
                i.invoice_number == inv and i.supplier_gstin == gstin
                and i.issue_type == ITCIssueType.EXCESS_CLAIMED
                for i in issues
            )
            if not already_excess:
                issues.append(ITCIssue(
                    supplier_gstin=gstin,
                    supplier_name=None,
                    invoice_number=inv,
                    invoice_date=date,
                    issue_type=ITCIssueType.SUPPLIER_NOT_FILED,
                    available_itc=available,
                    claimed_itc=Decimal("0"),
                    difference=available,
                    recommendation=(
                        f"Supplier {gstin} has not filed their GSTR-1. "
                        f"Your ITC of ₹{available:,.2f} is blocked until they file. "
                        f"Send them a reminder urgently."
                    ),
                ))

    # ── STEP 6: Sort and calculate totals ─────────────────────────────────
    type_order = {
        ITCIssueType.EXCESS_CLAIMED: 0,
        ITCIssueType.UNCLAIMED: 1,
        ITCIssueType.SUPPLIER_NOT_FILED: 2,
        ITCIssueType.RATE_DIFFERENCE: 3,
    }
    issues.sort(key=lambda i: (type_order.get(i.issue_type, 9), -i.difference))

    total_unclaimed = sum(
        (i.difference for i in issues if i.issue_type == ITCIssueType.UNCLAIMED),
        Decimal("0"),
    )
    total_excess = sum(
        (i.difference for i in issues if i.issue_type == ITCIssueType.EXCESS_CLAIMED),
        Decimal("0"),
    )
    total_at_risk = sum(
        (i.difference for i in issues if i.issue_type == ITCIssueType.SUPPLIER_NOT_FILED),
        Decimal("0"),
    )

    issues_by_type: dict[str, int] = {}
    for issue in issues:
        issues_by_type[issue.issue_type.value] = issues_by_type.get(issue.issue_type.value, 0) + 1

    elapsed = int(time.time() * 1000) - start_ms

    logger.info(
        "itc_analysis_complete",
        total_invoices_checked=total_invoices_checked,
        total_unclaimed_itc=str(total_unclaimed),
        total_excess_claimed=str(total_excess),
        total_at_risk=str(total_at_risk),
        issue_count=len(issues),
        processing_time_ms=elapsed,
    )

    return ITCAnalysisResult(
        total_invoices_checked=total_invoices_checked,
        total_unique_suppliers=len(all_gstins),
        total_unclaimed_itc=total_unclaimed,
        total_excess_claimed=total_excess,
        total_at_risk=total_at_risk,
        issues=issues,
        issues_by_type=issues_by_type,
        processing_time_ms=elapsed,
        warnings=warn_list,
    )
