"""Tests for app/services/parser.py — 8 test cases."""
import io
from decimal import Decimal

import pandas as pd
import pytest

from app.core.exceptions import ValidationError
from app.services.parser import (
    ParseResult,
    normalize_amount,
    normalize_date,
    normalize_gstin,
    parse_gstr1,
    parse_gstr3b,
    validate_excel_bytes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_xlsx_bytes(df: pd.DataFrame) -> bytes:
    """Serialise a DataFrame to an xlsx bytes object."""
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return buf.read()


def _gstr1_df(**overrides) -> pd.DataFrame:
    base = {
        "GSTIN of supplier": ["27AAPFU0939F1ZV"],
        "Invoice Number": ["INV-001"],
        "Invoice Date": ["01/04/2024"],
        "Taxable Value": [10000.00],
        "Integrated Tax Amount": [1800.00],
        "Central Tax Amount": [0.00],
        "State/UT Tax Amount": [0.00],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def _gstr3b_df(**overrides) -> pd.DataFrame:
    base = {
        "GSTIN of supplier": ["27AAPFU0939F1ZV"],
        "Invoice Number": ["INV-001"],
        "Invoice Date": ["01/04/2024"],
        "Taxable Value": [10000.00],
        "Integrated Tax Amount": [1800.00],
        "Central Tax Amount": [0.00],
        "State/UT Tax Amount": [0.00],
    }
    base.update(overrides)
    return pd.DataFrame(base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_validate_excel_bytes_valid_xlsx():
    xlsx_bytes = _make_xlsx_bytes(_gstr1_df())
    # Should not raise
    validate_excel_bytes(xlsx_bytes)


def test_validate_excel_bytes_invalid_file():
    with pytest.raises(ValidationError) as exc_info:
        validate_excel_bytes(b"This is not an Excel file at all")
    assert exc_info.value.code == "VAL_003"


def test_parse_gstr1_standard_format():
    xlsx = _make_xlsx_bytes(_gstr1_df())
    result: ParseResult = parse_gstr1(xlsx)
    assert result.invoice_count == 1
    assert len(result.dataframe) == 1
    row = result.dataframe.iloc[0]
    assert row["supplier_gstin"] == "27AAPFU0939F1ZV"
    assert row["invoice_number"] == "INV-001"
    assert row["taxable_value"] == Decimal("10000.00")
    assert row["igst_amount"] == Decimal("1800.00")


def test_parse_gstr1_missing_required_columns():
    df = pd.DataFrame({"Random Column": ["value1"], "Another Column": [123]})
    xlsx = _make_xlsx_bytes(df)
    with pytest.raises(ValidationError) as exc_info:
        parse_gstr1(xlsx)
    assert exc_info.value.code == "VAL_003"


def test_parse_gstr1_handles_blank_rows():
    """Rows with missing GSTIN or invoice number should be dropped with warnings."""
    df = _gstr1_df()
    # Append two bad rows
    bad_rows = pd.DataFrame({
        "GSTIN of supplier": [None, "INVALID"],
        "Invoice Number": ["INV-002", "INV-003"],
        "Invoice Date": [None, None],
        "Taxable Value": [500.00, 600.00],
        "Integrated Tax Amount": [90.00, 108.00],
        "Central Tax Amount": [0.00, 0.00],
        "State/UT Tax Amount": [0.00, 0.00],
    })
    combined = pd.concat([df, bad_rows], ignore_index=True)
    xlsx = _make_xlsx_bytes(combined)
    result = parse_gstr1(xlsx)
    # Only the one valid row should survive
    assert result.invoice_count == 1
    assert any("invalid or missing GSTIN" in w for w in result.warnings)


def test_normalize_gstin_lowercase():
    """normalize_gstin should upper-case and validate GSTIN format."""
    valid = normalize_gstin("27aapfu0939f1zv")
    assert valid == "27AAPFU0939F1ZV"

    invalid = normalize_gstin("INVALID")
    assert invalid is None

    none_val = normalize_gstin(None)
    assert none_val is None


def test_normalize_amount_string_with_commas():
    """normalize_amount must strip ₹ signs and commas before parsing."""
    assert normalize_amount("₹1,23,456.78") == Decimal("123456.78")
    assert normalize_amount("10,000") == Decimal("10000.00")
    assert normalize_amount(None) == Decimal("0")
    assert normalize_amount("garbage") == Decimal("0")
    assert normalize_amount(1234.56) == Decimal("1234.56")


def test_normalize_date_various_formats():
    """normalize_date must handle multiple real-world date formats."""
    assert normalize_date("01/04/2024") == "2024-04-01"
    assert normalize_date("2024-04-01") == "2024-04-01"
    assert normalize_date("01-Apr-2024") == "2024-04-01"
    assert normalize_date("01 Apr 2024") == "2024-04-01"
    assert normalize_date(None) is None
    assert normalize_date("") is None
