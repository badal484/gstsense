"""Tests for app/services/itc_analyzer.py — 13 test cases."""
from decimal import Decimal

import pandas as pd
import pytest

from app.services.itc_analyzer import ITCAnalysisResult, ITCIssueType, analyze_itc


def make_gstr3b_df(data: dict) -> pd.DataFrame:
    rows = []
    gstins = data.get("supplier_gstin", [])
    invs = data.get("invoice_number", [])
    igsts = data.get("igst_amount", [0] * len(gstins))
    cgsts = data.get("cgst_amount", [0] * len(gstins))
    sgsts = data.get("sgst_amount", [0] * len(gstins))
    for i in range(len(gstins)):
        rows.append({
            "supplier_gstin": gstins[i],
            "invoice_number": invs[i],
            "igst_amount": Decimal(str(igsts[i])),
            "cgst_amount": Decimal(str(cgsts[i])),
            "sgst_amount": Decimal(str(sgsts[i])),
        })
    return pd.DataFrame(rows)


def make_gstr2b_df(data: dict) -> pd.DataFrame:
    rows = []
    gstins = data.get("supplier_gstin", [])
    invs = data.get("invoice_number", [])
    igsts = data.get("igst_available", [0] * len(gstins))
    cgsts = data.get("cgst_available", [0] * len(gstins))
    sgsts = data.get("sgst_available", [0] * len(gstins))
    avail_flags = data.get("itc_availability", ["YES"] * len(gstins))
    filing_statuses = data.get("supplier_filing_status", ["Filed"] * len(gstins))
    for i in range(len(gstins)):
        igst = Decimal(str(igsts[i]))
        cgst = Decimal(str(cgsts[i]))
        sgst = Decimal(str(sgsts[i]))
        rows.append({
            "supplier_gstin": gstins[i],
            "invoice_number": invs[i],
            "igst_available": igst,
            "cgst_available": cgst,
            "sgst_available": sgst,
            "total_available_itc": igst + cgst + sgst,
            "itc_availability": avail_flags[i],
            "supplier_filing_status": filing_statuses[i],
            "invoice_date": None,
        })
    return pd.DataFrame(rows)


class TestITCAnalyzer:

    def test_perfect_match_zero_issues(self):
        g3b = make_gstr3b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_amount": [18000],
        })
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_available": [18000],
        })
        result = analyze_itc(g3b, g2b)
        assert len(result.issues) == 0
        assert result.total_unclaimed_itc == Decimal("0")
        assert result.total_excess_claimed == Decimal("0")

    def test_unclaimed_itc_detected(self):
        g3b = make_gstr3b_df({
            "supplier_gstin": [],
            "invoice_number": [],
        })
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_available": [18000],
        })
        result = analyze_itc(g3b, g2b)
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == ITCIssueType.UNCLAIMED
        assert result.issues[0].difference == Decimal("18000")
        assert result.total_unclaimed_itc == Decimal("18000")

    def test_partial_unclaimed_itc_detected(self):
        g3b = make_gstr3b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_amount": [9000],
        })
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_available": [18000],
        })
        result = analyze_itc(g3b, g2b)
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == ITCIssueType.UNCLAIMED
        assert result.issues[0].difference == Decimal("9000")
        assert result.issues[0].available_itc == Decimal("18000")
        assert result.issues[0].claimed_itc == Decimal("9000")

    def test_excess_claimed_detected(self):
        g3b = make_gstr3b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_amount": [18000],
        })
        g2b = make_gstr2b_df({
            "supplier_gstin": [],
            "invoice_number": [],
        })
        result = analyze_itc(g3b, g2b)
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == ITCIssueType.EXCESS_CLAIMED
        assert result.issues[0].difference == Decimal("18000")
        assert result.total_excess_claimed == Decimal("18000")

    def test_excess_claimed_over_available(self):
        g3b = make_gstr3b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_amount": [20000],
        })
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_available": [18000],
        })
        result = analyze_itc(g3b, g2b)
        excess = [i for i in result.issues if i.issue_type == ITCIssueType.EXCESS_CLAIMED]
        assert len(excess) == 1
        assert excess[0].difference == Decimal("2000")

    def test_supplier_not_filed_detected(self):
        g3b = make_gstr3b_df({"supplier_gstin": [], "invoice_number": []})
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_available": [9000],
            "itc_availability": ["YES"],
            "supplier_filing_status": ["Not Filed"],
        })
        result = analyze_itc(g3b, g2b)
        not_filed = [i for i in result.issues if i.issue_type == ITCIssueType.SUPPLIER_NOT_FILED]
        assert len(not_filed) == 1
        assert not_filed[0].supplier_gstin == "27AAPFU0939F1ZV"
        assert result.total_at_risk == Decimal("9000")

    def test_ineligible_itc_ignored(self):
        g3b = make_gstr3b_df({"supplier_gstin": [], "invoice_number": []})
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_available": [18000],
            "itc_availability": ["NO"],
        })
        result = analyze_itc(g3b, g2b)
        unclaimed = [i for i in result.issues if i.issue_type == ITCIssueType.UNCLAIMED]
        assert len(unclaimed) == 0

    def test_totals_calculated_correctly(self):
        g3b = make_gstr3b_df({"supplier_gstin": [], "invoice_number": []})
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV", "29AABCT1332L1ZT"],
            "invoice_number": ["INV-001", "INV-002"],
            "igst_available": [9000, 5000],
        })
        result = analyze_itc(g3b, g2b)
        assert result.total_unclaimed_itc == Decimal("14000")

    def test_issues_sorted_by_risk(self):
        g3b = make_gstr3b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-E"],
            "igst_amount": [5000],
        })
        g2b = make_gstr2b_df({
            "supplier_gstin": ["29AABCT1332L1ZT"],
            "invoice_number": ["INV-U"],
            "igst_available": [10000],
        })
        result = analyze_itc(g3b, g2b)
        types = [i.issue_type for i in result.issues]
        excess_idx = next((j for j, t in enumerate(types) if t == ITCIssueType.EXCESS_CLAIMED), None)
        unclaimed_idx = next((j for j, t in enumerate(types) if t == ITCIssueType.UNCLAIMED), None)
        if excess_idx is not None and unclaimed_idx is not None:
            assert excess_idx < unclaimed_idx

    def test_amount_within_tolerance_ignored(self):
        g3b = make_gstr3b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_amount": [18000],
        })
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_available": [18001],  # diff = 1.00, exactly at tolerance
        })
        result = analyze_itc(g3b, g2b)
        unclaimed = [i for i in result.issues if i.issue_type == ITCIssueType.UNCLAIMED]
        assert len(unclaimed) == 0

    def test_recommendations_contain_rupee_amount(self):
        g3b = make_gstr3b_df({"supplier_gstin": [], "invoice_number": []})
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_available": [18000],
        })
        result = analyze_itc(g3b, g2b)
        for issue in result.issues:
            assert "₹" in issue.recommendation

    def test_empty_gstr2b_returns_all_excess(self):
        g3b = make_gstr3b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_amount": [9000],
        })
        g2b = make_gstr2b_df({"supplier_gstin": [], "invoice_number": []})
        result = analyze_itc(g3b, g2b)
        assert all(i.issue_type == ITCIssueType.EXCESS_CLAIMED for i in result.issues)
        assert result.total_excess_claimed == Decimal("9000")

    def test_empty_gstr3b_returns_all_unclaimed(self):
        g3b = make_gstr3b_df({"supplier_gstin": [], "invoice_number": []})
        g2b = make_gstr2b_df({
            "supplier_gstin": ["27AAPFU0939F1ZV"],
            "invoice_number": ["INV-001"],
            "igst_available": [9000],
        })
        result = analyze_itc(g3b, g2b)
        assert all(i.issue_type == ITCIssueType.UNCLAIMED for i in result.issues)
        assert result.total_unclaimed_itc == Decimal("9000")
