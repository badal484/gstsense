"""Tests for app/services/reconciler.py — 8 test cases."""
from decimal import Decimal

import pandas as pd
import pytest

from app.models.mismatch import MismatchType
from app.services.reconciler import AMOUNT_TOLERANCE, MismatchDetail, reconcile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df(rows: list[dict]) -> pd.DataFrame:
    """Build a normalised DataFrame from a list of dicts (same shape as parser output)."""
    df = pd.DataFrame(rows)
    # Ensure Decimal types to mirror parser output
    for col in ["taxable_value", "igst_amount", "cgst_amount", "sgst_amount"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: Decimal(str(v)))
    df["total_tax"] = (
        df.get("igst_amount", Decimal("0"))
        + df.get("cgst_amount", Decimal("0"))
        + df.get("sgst_amount", Decimal("0"))
    )
    return df


GSTIN_A = "27AAPFU0939F1ZV"
GSTIN_B = "29AABCT3518Q1ZV"


def _row(gstin=GSTIN_A, inv="INV-001", tv="10000", igst="1800", cgst="0", sgst="0") -> dict:
    return {
        "supplier_gstin": gstin,
        "invoice_number": inv,
        "taxable_value": tv,
        "igst_amount": igst,
        "cgst_amount": cgst,
        "sgst_amount": sgst,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_perfect_match_zero_mismatches():
    row = _row()
    g1 = _df([row])
    g3b = _df([row])
    result = reconcile(g1, g3b)
    assert result.total_mismatches == 0
    assert result.total_rupee_risk == Decimal("0")
    assert result.mismatches == []


def test_missing_in_3b_detected():
    g1 = _df([_row(inv="INV-001")])
    g3b = _df([_row(inv="INV-002")])  # completely different invoice
    result = reconcile(g1, g3b)
    types = [m.mismatch_type for m in result.mismatches]
    assert MismatchType.missing_in_3b in types
    missing = next(m for m in result.mismatches if m.mismatch_type == MismatchType.missing_in_3b)
    assert missing.invoice_number == "INV-001"
    assert missing.rupee_difference == Decimal("10000.00")


def test_missing_in_1_detected():
    g1 = _df([_row(inv="INV-001")])
    g3b = _df([_row(inv="INV-002")])
    result = reconcile(g1, g3b)
    types = [m.mismatch_type for m in result.mismatches]
    assert MismatchType.missing_in_1 in types
    missing = next(m for m in result.mismatches if m.mismatch_type == MismatchType.missing_in_1)
    assert missing.invoice_number == "INV-002"


def test_value_mismatch_detected():
    g1 = _df([_row(tv="10000")])
    g3b = _df([_row(tv="8000")])  # ₹2000 difference — above tolerance
    result = reconcile(g1, g3b)
    types = [m.mismatch_type for m in result.mismatches]
    assert MismatchType.value_mismatch in types
    vm = next(m for m in result.mismatches if m.mismatch_type == MismatchType.value_mismatch)
    assert vm.rupee_difference == Decimal("2000.00")


def test_tax_mismatch_detected():
    g1 = _df([_row(igst="1800")])
    g3b = _df([_row(igst="900")])  # ₹900 tax difference — above tolerance
    result = reconcile(g1, g3b)
    types = [m.mismatch_type for m in result.mismatches]
    assert MismatchType.tax_mismatch in types
    tm = next(m for m in result.mismatches if m.mismatch_type == MismatchType.tax_mismatch)
    assert tm.rupee_difference == Decimal("900.00")


def test_amount_within_tolerance_not_flagged():
    """Differences at or below ₹1.00 must not generate a mismatch (rounding tolerance)."""
    g1 = _df([_row(tv="10000.50")])
    g3b = _df([_row(tv="10000.00")])  # ₹0.50 diff — within AMOUNT_TOLERANCE
    result = reconcile(g1, g3b)
    value_mismatches = [m for m in result.mismatches if m.mismatch_type == MismatchType.value_mismatch]
    assert value_mismatches == []


def test_rupee_risk_calculated_correctly():
    """total_rupee_risk must be the sum of all individual rupee_differences."""
    g1 = _df([_row(inv="INV-001", tv="5000"), _row(inv="INV-002", tv="3000")])
    g3b = _df([])  # both invoices missing from GSTR-3B
    result = reconcile(g1, g3b)
    assert result.total_rupee_risk == Decimal("8000.00")
    assert result.total_mismatches == 2


def test_results_sorted_by_rupee_difference_desc():
    """Mismatches must be ordered highest rupee_difference first."""
    g1 = _df([
        _row(inv="INV-001", tv="1000"),
        _row(inv="INV-002", tv="5000"),
        _row(inv="INV-003", tv="2500"),
    ])
    g3b = _df([])  # all missing
    result = reconcile(g1, g3b)
    diffs = [m.rupee_difference for m in result.mismatches]
    assert diffs == sorted(diffs, reverse=True)
    assert diffs[0] == Decimal("5000.00")
