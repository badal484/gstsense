import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import pandas as pd

from app.core.logging import get_logger
from app.models.mismatch import MismatchType

logger = get_logger(__name__)

AMOUNT_TOLERANCE = Decimal("1.00")


@dataclass
class MismatchDetail:
    invoice_number: str
    supplier_gstin: str
    mismatch_type: MismatchType
    gstr1_taxable_value: Decimal
    gstr3b_taxable_value: Decimal
    gstr1_tax_amount: Decimal
    gstr3b_tax_amount: Decimal
    rupee_difference: Decimal
    ai_explanation: Optional[str] = None


@dataclass
class ReconciliationResult:
    total_invoices_scanned: int
    total_unique_suppliers: int
    total_mismatches: int
    total_rupee_risk: Decimal
    mismatches_by_type: dict[str, int]
    mismatches: list[MismatchDetail]
    processing_time_ms: int
    warnings: list[str] = field(default_factory=list)


def build_invoice_key(gstin: str, invoice_number: str) -> str:
    """Return a unique lookup key: GSTIN|INVOICE_NUMBER (both uppercased)."""
    return f"{gstin.strip().upper()}|{invoice_number.strip().upper()}"


def reconcile(
    gstr1_df: pd.DataFrame,
    gstr3b_df: pd.DataFrame,
    warnings: Optional[list[str]] = None,
) -> ReconciliationResult:
    """Compare GSTR-1 and GSTR-3B DataFrames and return all mismatches."""
    start_ms = int(time.monotonic() * 1000)
    all_warnings: list[str] = list(warnings or [])
    mismatches: list[MismatchDetail] = []

    # Handle empty DataFrames gracefully
    if gstr1_df.empty and gstr3b_df.empty:
        return ReconciliationResult(
            total_invoices_scanned=0,
            total_unique_suppliers=0,
            total_mismatches=0,
            total_rupee_risk=Decimal("0"),
            mismatches_by_type={},
            mismatches=[],
            processing_time_ms=0,
            warnings=all_warnings,
        )

    # ------------------------------------------------------------------
    # STEP 1: Build lookup dictionaries keyed by GSTIN|InvoiceNumber
    # ------------------------------------------------------------------

    def _to_lookup(df: pd.DataFrame) -> dict[str, dict]:
        lookup: dict[str, dict] = {}
        for _, row in df.iterrows():
            gstin = row["supplier_gstin"]
            inv = row["invoice_number"]
            if gstin is None or inv is None:
                continue
            key = build_invoice_key(str(gstin), str(inv))
            lookup[key] = {
                "invoice_number": str(inv),
                "supplier_gstin": str(gstin),
                "taxable_value": Decimal(str(row["taxable_value"])),
                "total_tax": Decimal(str(row["total_tax"])),
            }
        return lookup

    gstr1_lookup = _to_lookup(gstr1_df)
    gstr3b_lookup = _to_lookup(gstr3b_df)

    logger.info(
        "reconciliation_started",
        gstr1_invoices=len(gstr1_lookup),
        gstr3b_invoices=len(gstr3b_lookup),
    )

    # ------------------------------------------------------------------
    # STEP 2: MISSING_IN_3B — in GSTR-1 but not in GSTR-3B
    # ------------------------------------------------------------------

    for key, r1 in gstr1_lookup.items():
        if key not in gstr3b_lookup:
            mismatches.append(
                MismatchDetail(
                    invoice_number=r1["invoice_number"],
                    supplier_gstin=r1["supplier_gstin"],
                    mismatch_type=MismatchType.missing_in_3b,
                    gstr1_taxable_value=r1["taxable_value"],
                    gstr3b_taxable_value=Decimal("0"),
                    gstr1_tax_amount=r1["total_tax"],
                    gstr3b_tax_amount=Decimal("0"),
                    rupee_difference=abs(r1["taxable_value"]),
                )
            )

    # ------------------------------------------------------------------
    # STEP 3: MISSING_IN_1 — in GSTR-3B but not in GSTR-1
    # ------------------------------------------------------------------

    for key, r3b in gstr3b_lookup.items():
        if key not in gstr1_lookup:
            mismatches.append(
                MismatchDetail(
                    invoice_number=r3b["invoice_number"],
                    supplier_gstin=r3b["supplier_gstin"],
                    mismatch_type=MismatchType.missing_in_1,
                    gstr1_taxable_value=Decimal("0"),
                    gstr3b_taxable_value=r3b["taxable_value"],
                    gstr1_tax_amount=Decimal("0"),
                    gstr3b_tax_amount=r3b["total_tax"],
                    rupee_difference=abs(r3b["taxable_value"]),
                )
            )

    # ------------------------------------------------------------------
    # STEP 4 & 5: VALUE_MISMATCH and TAX_MISMATCH for matched invoices
    # ------------------------------------------------------------------

    for key in gstr1_lookup:
        if key not in gstr3b_lookup:
            continue
        r1 = gstr1_lookup[key]
        r3b = gstr3b_lookup[key]

        value_diff = abs(r1["taxable_value"] - r3b["taxable_value"])
        if value_diff > AMOUNT_TOLERANCE:
            mismatches.append(
                MismatchDetail(
                    invoice_number=r1["invoice_number"],
                    supplier_gstin=r1["supplier_gstin"],
                    mismatch_type=MismatchType.value_mismatch,
                    gstr1_taxable_value=r1["taxable_value"],
                    gstr3b_taxable_value=r3b["taxable_value"],
                    gstr1_tax_amount=r1["total_tax"],
                    gstr3b_tax_amount=r3b["total_tax"],
                    rupee_difference=value_diff,
                )
            )

        tax_diff = abs(r1["total_tax"] - r3b["total_tax"])
        if tax_diff > AMOUNT_TOLERANCE:
            mismatches.append(
                MismatchDetail(
                    invoice_number=r1["invoice_number"],
                    supplier_gstin=r1["supplier_gstin"],
                    mismatch_type=MismatchType.tax_mismatch,
                    gstr1_taxable_value=r1["taxable_value"],
                    gstr3b_taxable_value=r3b["taxable_value"],
                    gstr1_tax_amount=r1["total_tax"],
                    gstr3b_tax_amount=r3b["total_tax"],
                    rupee_difference=tax_diff,
                )
            )

    # ------------------------------------------------------------------
    # STEP 6: Calculate summary totals
    # ------------------------------------------------------------------

    all_keys = set(gstr1_lookup) | set(gstr3b_lookup)
    all_gstins = set()
    for key in all_keys:
        gstin = key.split("|")[0]
        all_gstins.add(gstin)

    total_rupee_risk = sum(
        (m.rupee_difference for m in mismatches), Decimal("0")
    )

    mismatches_by_type: dict[str, int] = {}
    for m in mismatches:
        k = m.mismatch_type.value
        mismatches_by_type[k] = mismatches_by_type.get(k, 0) + 1

    # Sort highest rupee risk first
    mismatches.sort(key=lambda m: m.rupee_difference, reverse=True)

    elapsed_ms = int(time.monotonic() * 1000) - start_ms

    # STEP 7: Log summary
    logger.info(
        "reconciliation_complete",
        invoices_scanned=len(all_keys),
        mismatches_found=len(mismatches),
        rupee_risk=str(total_rupee_risk),
        processing_time_ms=elapsed_ms,
    )

    return ReconciliationResult(
        total_invoices_scanned=len(all_keys),
        total_unique_suppliers=len(all_gstins),
        total_mismatches=len(mismatches),
        total_rupee_risk=total_rupee_risk,
        mismatches_by_type=mismatches_by_type,
        mismatches=mismatches,
        processing_time_ms=elapsed_ms,
        warnings=all_warnings,
    )
