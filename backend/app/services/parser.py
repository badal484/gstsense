import io
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

import pandas as pd

from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Magic-byte signatures for Excel files
# ---------------------------------------------------------------------------

EXCEL_SIGNATURES = [
    b"\x50\x4B\x03\x04",  # .xlsx (ZIP-based Office Open XML)
    b"\x50\x4B\x05\x06",
    b"\x50\x4B\x07\x08",
    b"\xD0\xCF\x11\xE0",  # .xls (Compound Document Binary)
]

GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)

# ---------------------------------------------------------------------------
# Column name variant mappings
# ---------------------------------------------------------------------------

GSTR1_COLUMN_VARIANTS: dict[str, list[str]] = {
    "supplier_gstin": [
        "GSTIN of supplier",
        "Supplier GSTIN",
        "GSTIN",
        "gstin",
        "Supplier Gstin",
        "GSTIN/UIN of Recipient",
        "GSTIN of Recipient",
    ],
    "invoice_number": [
        "Invoice Number",
        "Invoice No",
        "Invoice No.",
        "Inv No",
        "invoice_number",
        "Document Number",
    ],
    "invoice_date": [
        "Invoice Date",
        "Invoice Dt",
        "Date",
        "invoice_date",
        "Document Date",
    ],
    "taxable_value": [
        "Taxable Value",
        "Taxable Amount",
        "Total Taxable Value",
        "taxable_value",
        "Value",
    ],
    "igst_amount": [
        "Integrated Tax Amount",
        "IGST Amount",
        "IGST",
        "igst_amount",
        "Integrated Tax",
    ],
    "cgst_amount": [
        "Central Tax Amount",
        "CGST Amount",
        "CGST",
        "cgst_amount",
        "Central Tax",
    ],
    "sgst_amount": [
        "State/UT Tax Amount",
        "SGST Amount",
        "SGST",
        "sgst_amount",
        "State Tax",
        "UT Tax Amount",
    ],
}

GSTR3B_COLUMN_VARIANTS: dict[str, list[str]] = {
    "supplier_gstin": [
        "GSTIN of supplier",
        "Supplier GSTIN",
        "GSTIN",
        "gstin",
    ],
    "invoice_number": [
        "Invoice Number",
        "Invoice No",
        "Invoice No.",
        "invoice_number",
    ],
    "invoice_date": [
        "Invoice Date",
        "Date",
        "invoice_date",
    ],
    "taxable_value": [
        "Taxable Value",
        "Taxable Amount",
        "taxable_value",
    ],
    "igst_amount": [
        "Integrated Tax Amount",
        "IGST Amount",
        "IGST",
        "igst_amount",
    ],
    "cgst_amount": [
        "Central Tax Amount",
        "CGST Amount",
        "CGST",
        "cgst_amount",
    ],
    "sgst_amount": [
        "State/UT Tax Amount",
        "SGST Amount",
        "SGST",
        "sgst_amount",
    ],
}

_DATE_FORMATS = [
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%m/%d/%Y",
    "%d/%m/%y",
]


@dataclass
class ParseResult:
    dataframe: pd.DataFrame
    invoice_count: int
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_excel_bytes(file_bytes: bytes) -> None:
    """Raise ValidationError(VAL_003) if bytes lack an Excel magic signature."""
    header = file_bytes[:8]
    for sig in EXCEL_SIGNATURES:
        if header[: len(sig)] == sig:
            return
    raise ValidationError(
        message="File is not a valid Excel document (.xlsx or .xls). Please upload the correct file.",
        code="VAL_003",
    )


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------


def find_header_row(
    df_raw: pd.DataFrame,
    column_variants: Optional[dict[str, list[str]]] = None,
) -> int:
    """Return the row index that most likely contains column headers."""
    if column_variants is None:
        column_variants = GSTR1_COLUMN_VARIANTS

    all_variants: set[str] = set()
    for variants in column_variants.values():
        all_variants.update(v.lower().strip() for v in variants)

    best_row = 0
    best_count = 0

    for i in range(min(10, len(df_raw))):
        row_values: list[str] = []
        for v in df_raw.iloc[i]:
            try:
                if not pd.isna(v):
                    row_values.append(str(v).strip().lower())
            except (TypeError, ValueError):
                row_values.append(str(v).strip().lower())

        count = sum(1 for v in row_values if v in all_variants)
        if count > best_count:
            best_count = count
            best_row = i

    return best_row


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------


def map_columns(
    df: pd.DataFrame,
    column_variants: dict[str, list[str]],
) -> dict[str, str]:
    """Return {standard_name: actual_column_name}.

    Raises ValidationError(VAL_003) when required columns are missing.
    """
    reverse: dict[str, str] = {}
    for std_name, variants in column_variants.items():
        for v in variants:
            reverse[v.lower().strip()] = std_name

    mapping: dict[str, str] = {}
    for col in df.columns:
        key = str(col).strip().lower()
        std = reverse.get(key)
        if std and std not in mapping:
            mapping[std] = col

    required = ["supplier_gstin", "invoice_number", "taxable_value"]
    missing = [r for r in required if r not in mapping]
    if missing:
        raise ValidationError(
            message=(
                f"Required columns not found: {missing}. "
                "Check that the file is in the correct GSTR format."
            ),
            code="VAL_003",
        )
    return mapping


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def normalize_gstin(value: object) -> Optional[str]:
    """Return uppercase GSTIN or None for invalid/blank cells."""
    try:
        if pd.isna(value):  # type: ignore[arg-type, unused-ignore]
            return None
    except (TypeError, ValueError):
        pass
    if value is None:
        return None
    s = str(value).strip().upper()
    if not s or not GSTIN_PATTERN.match(s):
        return None
    return s


def normalize_invoice_number(value: object) -> Optional[str]:
    """Return clean uppercase invoice number or None for blank cells."""
    try:
        if pd.isna(value):  # type: ignore[arg-type, unused-ignore]
            return None
    except (TypeError, ValueError):
        pass
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return str(int(value)).strip().upper()
    return str(value).strip().upper() or None


def normalize_amount(value: object) -> Decimal:
    """Return Decimal(value, 2 dp); returns Decimal('0') on any error."""
    try:
        if pd.isna(value):  # type: ignore[arg-type, unused-ignore]
            return Decimal("0")
    except (TypeError, ValueError):
        pass
    if value is None:
        return Decimal("0")
    try:
        s = str(value).strip().replace("₹", "").replace(",", "").strip()
        if not s:
            return Decimal("0")
        return Decimal(s).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def normalize_date(value: object) -> Optional[str]:
    """Return ISO-8601 date string (YYYY-MM-DD) or None."""
    try:
        if pd.isna(value):  # type: ignore[arg-type, unused-ignore]
            return None
    except (TypeError, ValueError):
        pass
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    # For strings: try explicit formats first (pd.Timestamp uses US MM/DD ambiguity)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None
    # For non-string non-datetime (e.g. pd.Timestamp from Excel): use pandas
    try:
        ts = pd.Timestamp(value)
        if pd.isna(ts):
            return None
        return str(ts.strftime("%Y-%m-%d"))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Shared parse pipeline
# ---------------------------------------------------------------------------


def _parse_excel(
    file_bytes: bytes,
    column_variants: dict[str, list[str]],
    file_label: str,
) -> ParseResult:
    validate_excel_bytes(file_bytes)
    warnings: list[str] = []

    try:
        df_raw = pd.read_excel(
            io.BytesIO(file_bytes),
            header=None,
            nrows=15,
            engine="openpyxl",
        )
    except Exception as exc:
        raise ValidationError(
            message=f"Cannot read {file_label} file: {exc}",
            code="VAL_003",
        )

    header_row = find_header_row(df_raw, column_variants)
    logger.info(f"{file_label}_header_detected", header_row=header_row)

    try:
        df = pd.read_excel(
            io.BytesIO(file_bytes),
            header=header_row,
            engine="openpyxl",
        )
    except Exception as exc:
        raise ValidationError(
            message=f"Cannot read {file_label} file: {exc}",
            code="VAL_003",
        )

    logger.info(f"{file_label}_raw_rows", count=len(df))

    col_map = map_columns(df, column_variants)

    result: dict[str, object] = {std: df[actual] for std, actual in col_map.items()}
    result_df = pd.DataFrame(result)

    # Fill optional columns that may be absent in the file
    for amt_col in ["igst_amount", "cgst_amount", "sgst_amount"]:
        if amt_col not in result_df.columns:
            result_df[amt_col] = Decimal("0")

    if "invoice_date" not in result_df.columns:
        result_df["invoice_date"] = None

    # Normalise
    result_df["supplier_gstin"] = result_df["supplier_gstin"].apply(normalize_gstin)
    result_df["invoice_number"] = result_df["invoice_number"].apply(normalize_invoice_number)
    result_df["invoice_date"] = result_df["invoice_date"].apply(normalize_date)
    result_df["taxable_value"] = result_df["taxable_value"].apply(normalize_amount)
    result_df["igst_amount"] = result_df["igst_amount"].apply(normalize_amount)
    result_df["cgst_amount"] = result_df["cgst_amount"].apply(normalize_amount)
    result_df["sgst_amount"] = result_df["sgst_amount"].apply(normalize_amount)

    result_df["total_tax"] = (
        result_df["igst_amount"]
        + result_df["cgst_amount"]
        + result_df["sgst_amount"]
    )

    before = len(result_df)
    result_df = result_df[result_df["supplier_gstin"].notna()]
    dropped = before - len(result_df)
    if dropped:
        warnings.append(f"Dropped {dropped} rows with invalid or missing GSTIN")
        logger.info(f"{file_label}_gstin_rows_dropped", count=dropped)

    before = len(result_df)
    result_df = result_df[result_df["invoice_number"].notna()]
    dropped = before - len(result_df)
    if dropped:
        warnings.append(f"Dropped {dropped} rows with missing invoice number")
        logger.info(f"{file_label}_invoice_rows_dropped", count=dropped)

    before = len(result_df)
    result_df = result_df.drop_duplicates()
    dropped = before - len(result_df)
    if dropped:
        warnings.append(f"Dropped {dropped} duplicate rows")
        logger.info(f"{file_label}_duplicate_rows_dropped", count=dropped)

    if len(result_df) == 0:
        raise ValidationError(
            message=(
                f"No valid invoices found in {file_label} file after cleaning. "
                "Ensure the file contains valid GSTINs and invoice numbers."
            ),
            code="VAL_003",
        )

    result_df = result_df.reset_index(drop=True)
    logger.info(f"{file_label}_parsed", invoice_count=len(result_df))

    return ParseResult(
        dataframe=result_df,
        invoice_count=len(result_df),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_gstr1(file_bytes: bytes) -> ParseResult:
    """Parse a GSTR-1 Excel file into a clean, normalised DataFrame."""
    return _parse_excel(file_bytes, GSTR1_COLUMN_VARIANTS, "GSTR-1")


def parse_gstr3b(file_bytes: bytes) -> ParseResult:
    """Parse a GSTR-3B Excel file into a clean, normalised DataFrame."""
    return _parse_excel(file_bytes, GSTR3B_COLUMN_VARIANTS, "GSTR-3B")
