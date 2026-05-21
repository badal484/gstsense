"""Compliance health score unit tests."""

from decimal import Decimal

import pytest

from app.services.compliance_score import calculate_compliance_score, get_compliance_grade


class TestComplianceScore:
    def test_perfect_compliance_score_100(self):
        """Zero issues + bonuses gives maximum score (capped at 100)."""
        score = calculate_compliance_score(
            total_mismatches_last_3_months=0,
            total_rupee_risk_last_3_months=Decimal("0"),
            scans_run_last_3_months=3,
            has_pending_notices=False,
            itc_leakage_amount=Decimal("0"),
            days_since_last_scan=5,
            subscription_active=True,
        )
        assert score.score == 100
        assert score.grade == "A+"

    def test_many_mismatches_reduces_score(self):
        """21+ mismatches deducts 50 points."""
        score = calculate_compliance_score(
            total_mismatches_last_3_months=25,
            total_rupee_risk_last_3_months=Decimal("0"),
            scans_run_last_3_months=1,
            has_pending_notices=False,
            itc_leakage_amount=Decimal("0"),
            days_since_last_scan=5,
            subscription_active=False,
        )
        # 100 - 50 (mismatches) + 5 (scanned_recently) = 55
        assert score.score == 55
        assert score.grade == "C"

    def test_high_rupee_risk_reduces_score(self):
        """₹5L+ risk deducts 35 points."""
        score = calculate_compliance_score(
            total_mismatches_last_3_months=0,
            total_rupee_risk_last_3_months=Decimal("600000"),
            scans_run_last_3_months=1,
            has_pending_notices=False,
            itc_leakage_amount=Decimal("0"),
            days_since_last_scan=5,
            subscription_active=False,
        )
        # 100 - 35 (risk) + 5 (scan) = 70
        assert score.score == 70
        assert score.grade == "B"

    def test_pending_notice_deducts_20(self):
        """Pending notice deducts 20 points."""
        score = calculate_compliance_score(
            total_mismatches_last_3_months=0,
            total_rupee_risk_last_3_months=Decimal("0"),
            scans_run_last_3_months=1,
            has_pending_notices=True,
            itc_leakage_amount=Decimal("0"),
            days_since_last_scan=5,
            subscription_active=False,
        )
        # 100 - 20 (notice) + 5 (scan) = 85
        assert score.score == 85
        assert score.grade == "A"

    def test_never_scanned_deducts_20(self):
        """Never scanned deducts 20 points."""
        score = calculate_compliance_score(
            total_mismatches_last_3_months=0,
            total_rupee_risk_last_3_months=Decimal("0"),
            scans_run_last_3_months=0,
            has_pending_notices=False,
            itc_leakage_amount=Decimal("0"),
            days_since_last_scan=None,
            subscription_active=False,
        )
        # 100 - 20 (never scanned) = 80
        assert score.score == 80
        assert score.grade == "A"

    def test_score_never_goes_below_zero(self):
        """Score floor is 0 even with all penalties stacked."""
        score = calculate_compliance_score(
            total_mismatches_last_3_months=100,
            total_rupee_risk_last_3_months=Decimal("10000000"),
            scans_run_last_3_months=0,
            has_pending_notices=True,
            itc_leakage_amount=Decimal("1000000"),
            days_since_last_scan=None,
            subscription_active=False,
        )
        # 100 - 50 - 35 - 20 - 15 - 20 = -40 → floor 0
        assert score.score == 0
        assert score.grade == "D"

    def test_score_never_exceeds_100(self):
        """Score ceiling is 100."""
        score = calculate_compliance_score(
            total_mismatches_last_3_months=0,
            total_rupee_risk_last_3_months=Decimal("0"),
            scans_run_last_3_months=10,
            has_pending_notices=False,
            itc_leakage_amount=Decimal("0"),
            days_since_last_scan=1,
            subscription_active=True,
        )
        # 100 + 5 (scan) + 5 (subscription) = 110 → ceiling 100
        assert score.score == 100

    def test_grade_a_plus_for_90_plus(self):
        """Score 90+ gives A+ grade."""
        grade, color = get_compliance_grade(95)
        assert grade == "A+"
        assert color == "#1D9E75"

        grade90, _ = get_compliance_grade(90)
        assert grade90 == "A+"

    def test_grade_d_for_below_45(self):
        """Score below 45 gives D grade."""
        grade, color = get_compliance_grade(44)
        assert grade == "D"
        assert color == "#E24B4A"

        grade0, _ = get_compliance_grade(0)
        assert grade0 == "D"

    def test_recommendations_present_for_low_score(self):
        """Low score should include actionable recommendations."""
        score = calculate_compliance_score(
            total_mismatches_last_3_months=30,
            total_rupee_risk_last_3_months=Decimal("0"),
            scans_run_last_3_months=0,
            has_pending_notices=True,
            itc_leakage_amount=Decimal("100000"),
            days_since_last_scan=None,
            subscription_active=False,
        )
        assert len(score.recommendations) > 0
        # Should mention mismatches and notices
        joined = " ".join(score.recommendations)
        assert "notice" in joined.lower() or "scan" in joined.lower() or "ITC" in joined or "mismatch" in joined.lower()

    def test_factors_list_not_empty(self):
        """Factors list should always have entries."""
        score = calculate_compliance_score(
            total_mismatches_last_3_months=0,
            total_rupee_risk_last_3_months=Decimal("0"),
            scans_run_last_3_months=1,
            has_pending_notices=False,
            itc_leakage_amount=Decimal("0"),
            days_since_last_scan=10,
            subscription_active=True,
        )
        assert len(score.factors) > 0
        for f in score.factors:
            assert "name" in f
            assert "status" in f
            assert "description" in f
            assert "points" in f

    def test_subscription_bonus_adds_5(self):
        """Active subscription adds 5 points vs no subscription."""
        base = calculate_compliance_score(
            total_mismatches_last_3_months=5,
            total_rupee_risk_last_3_months=Decimal("0"),
            scans_run_last_3_months=1,
            has_pending_notices=False,
            itc_leakage_amount=Decimal("0"),
            days_since_last_scan=15,
            subscription_active=False,
        )
        with_sub = calculate_compliance_score(
            total_mismatches_last_3_months=5,
            total_rupee_risk_last_3_months=Decimal("0"),
            scans_run_last_3_months=1,
            has_pending_notices=False,
            itc_leakage_amount=Decimal("0"),
            days_since_last_scan=15,
            subscription_active=True,
        )
        assert with_sub.score == base.score + 5
