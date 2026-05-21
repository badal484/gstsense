from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.logging import get_logger

logger = get_logger(__name__)

BRAND_PURPLE = HexColor("#534AB7")
BRAND_TEAL = HexColor("#1D9E75")
RISK_RED = HexColor("#E24B4A")
LIGHT_GRAY = HexColor("#F1EFE8")
DARK_GRAY = HexColor("#444441")
AMBER = HexColor("#BA7517")
WHITE = HexColor("#FFFFFF")
CRITICAL_RED = HexColor("#8B0000")

MISMATCH_TYPE_LABELS = {
    "missing_in_3b": "Missing in 3B",
    "missing_in_1": "Missing in 1",
    "value_mismatch": "Value Mismatch",
    "tax_mismatch": "Tax Mismatch",
}

MISMATCH_TYPE_COLORS = {
    "missing_in_3b": RISK_RED,
    "missing_in_1": RISK_RED,
    "value_mismatch": AMBER,
    "tax_mismatch": AMBER,
}

DISCLAIMER_TEXT = (
    "This report is generated for informational purposes only. "
    "All findings must be verified with your Chartered Accountant before taking any action. "
    "GSTSense does not constitute legal or tax advice."
)

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm


@dataclass
class ReportData:
    organization_name: str
    gstin: str
    scan_month: str
    total_invoices_scanned: int
    total_mismatches: int
    total_rupee_risk: Decimal
    mismatches: list[dict]
    generated_at: datetime


def _format_rupees(amount: Decimal) -> str:
    if amount < 0:
        amount = abs(amount)
    amount_str = f"{amount:.2f}"
    integer_part, decimal_part = amount_str.split(".")
    if len(integer_part) <= 3:
        return f"₹{integer_part}.{decimal_part}"
    result = integer_part[-3:]
    remaining = integer_part[:-3]
    while remaining:
        result = remaining[-2:] + "," + result
        remaining = remaining[:-2]
    return f"₹{result}.{decimal_part}"


def _format_month(scan_month: str) -> str:
    try:
        dt = datetime.strptime(scan_month, "%Y-%m")
        return dt.strftime("%B %Y")
    except ValueError:
        return scan_month


def _format_date(dt: datetime) -> str:
    return dt.strftime("%d %B %Y")


def _get_risk_level(total_rupee_risk: Decimal) -> tuple[str, HexColor]:
    if total_rupee_risk < Decimal("10000"):
        return "LOW", BRAND_TEAL
    if total_rupee_risk < Decimal("100000"):
        return "MEDIUM", AMBER
    if total_rupee_risk < Decimal("500000"):
        return "HIGH", RISK_RED
    return "CRITICAL", CRITICAL_RED


def _build_styles() -> dict[str, ParagraphStyle]:
    styles: dict[str, ParagraphStyle] = {}
    styles["section_title"] = ParagraphStyle(
        "section_title", fontName="Helvetica-Bold", fontSize=12,
        textColor=BRAND_PURPLE, spaceBefore=8, spaceAfter=6, leading=16,
    )
    styles["body"] = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9, textColor=DARK_GRAY, leading=13,
    )
    styles["label"] = ParagraphStyle(
        "label", fontName="Helvetica-Bold", fontSize=9, textColor=DARK_GRAY, leading=13,
    )
    styles["stat_label"] = ParagraphStyle(
        "stat_label", fontName="Helvetica", fontSize=8, textColor=DARK_GRAY,
        alignment=TA_CENTER, leading=11,
    )
    styles["explanation_box"] = ParagraphStyle(
        "explanation_box", fontName="Helvetica", fontSize=8, textColor=DARK_GRAY,
        leading=12, leftIndent=4, rightIndent=4,
    )
    styles["table_header"] = ParagraphStyle(
        "table_header", fontName="Helvetica-Bold", fontSize=8, textColor=WHITE,
        alignment=TA_CENTER, leading=11,
    )
    styles["table_cell"] = ParagraphStyle(
        "table_cell", fontName="Helvetica", fontSize=8, textColor=DARK_GRAY,
        alignment=TA_LEFT, leading=11,
    )
    styles["table_cell_center"] = ParagraphStyle(
        "table_cell_center", fontName="Helvetica", fontSize=8, textColor=DARK_GRAY,
        alignment=TA_CENTER, leading=11,
    )
    styles["table_cell_right"] = ParagraphStyle(
        "table_cell_right", fontName="Helvetica", fontSize=8, textColor=DARK_GRAY,
        alignment=TA_RIGHT, leading=11,
    )
    return styles


class _ReportBuilder:
    def __init__(self, data: ReportData) -> None:
        self.data = data
        self.styles = _build_styles()

    def _on_page(self, canvas, doc) -> None:  # type: ignore[no-untyped-def]
        canvas.saveState()
        header_y = PAGE_H - MARGIN + 2 * mm

        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(BRAND_PURPLE)
        canvas.drawString(MARGIN, header_y, "GSTSense")

        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(DARK_GRAY)
        canvas.drawRightString(PAGE_W - MARGIN, header_y, "GST Mismatch Report")

        canvas.setStrokeColor(BRAND_PURPLE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, header_y - 4 * mm, PAGE_W - MARGIN, header_y - 4 * mm)

        footer_y = MARGIN - 5 * mm
        canvas.setStrokeColor(LIGHT_GRAY)
        canvas.line(MARGIN, footer_y + 8 * mm, PAGE_W - MARGIN, footer_y + 8 * mm)

        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(DARK_GRAY)
        canvas.drawString(MARGIN, footer_y + 4 * mm, "Generated by GSTSense — gstsense.in")
        canvas.drawCentredString(PAGE_W / 2, footer_y + 4 * mm, f"Page {doc.page}")
        canvas.drawRightString(PAGE_W - MARGIN, footer_y + 4 * mm, _format_date(self.data.generated_at))

        canvas.setFont("Helvetica-Oblique", 6.5)
        canvas.drawCentredString(PAGE_W / 2, footer_y, DISCLAIMER_TEXT)

        canvas.restoreState()

    def _section_business_details(self) -> list:
        s = self.styles
        elements: list = []
        elements.append(Paragraph("Business Details", s["section_title"]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
        elements.append(Spacer(1, 4 * mm))

        left_data = [
            [Paragraph("Business Name:", s["label"]), Paragraph(self.data.organization_name, s["body"])],
            [Paragraph("GSTIN:", s["label"]), Paragraph(self.data.gstin, s["body"])],
            [Paragraph("Filing Period:", s["label"]), Paragraph(_format_month(self.data.scan_month), s["body"])],
        ]
        right_data = [
            [Paragraph("Report Date:", s["label"]), Paragraph(_format_date(self.data.generated_at), s["body"])],
            [Paragraph("Total Invoices Scanned:", s["label"]), Paragraph(str(self.data.total_invoices_scanned), s["body"])],
        ]

        cell_style = TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ])
        left_tbl = Table(left_data, colWidths=[4.2 * cm, 7 * cm])
        left_tbl.setStyle(cell_style)
        right_tbl = Table(right_data, colWidths=[4.8 * cm, 5 * cm])
        right_tbl.setStyle(cell_style)

        combined = Table([[left_tbl, right_tbl]], colWidths=[11.5 * cm, 10 * cm])
        combined.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        elements.append(combined)
        elements.append(Spacer(1, 6 * mm))
        return elements

    def _section_summary(self) -> list:
        s = self.styles
        elements: list = []
        elements.append(Paragraph("Scan Summary", s["section_title"]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
        elements.append(Spacer(1, 4 * mm))

        risk_label, risk_color = _get_risk_level(self.data.total_rupee_risk)

        def _num_style(color: HexColor, size: int) -> ParagraphStyle:
            return ParagraphStyle(
                f"ns_{id(color)}_{size}", fontName="Helvetica-Bold", fontSize=size,
                textColor=color, alignment=TA_CENTER, leading=size + 4,
            )

        m_color = RISK_RED if self.data.total_mismatches > 0 else BRAND_TEAL
        r_color = RISK_RED if self.data.total_rupee_risk > 0 else BRAND_TEAL

        cards = [
            Table([
                [Paragraph(str(self.data.total_mismatches), _num_style(m_color, 28))],
                [Paragraph("Mismatches Found", s["stat_label"])],
            ], colWidths=[6 * cm]),
            Table([
                [Paragraph(_format_rupees(self.data.total_rupee_risk), _num_style(r_color, 18))],
                [Paragraph("Total Rupee Risk", s["stat_label"])],
            ], colWidths=[8 * cm]),
            Table([
                [Paragraph(risk_label, _num_style(risk_color, 22))],
                [Paragraph("Risk Level", s["stat_label"])],
            ], colWidths=[5.5 * cm]),
        ]
        card_style = TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
        for c in cards:
            c.setStyle(card_style)

        summary_row = Table([cards], colWidths=[6.5 * cm, 8.5 * cm, 6 * cm])
        summary_row.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEAFTER", (0, 0), (1, 0), 0.5, DARK_GRAY),
        ]))
        elements.append(summary_row)
        elements.append(Spacer(1, 8 * mm))
        return elements

    def _section_table(self) -> list:
        s = self.styles
        elements: list = []
        if not self.data.mismatches:
            return elements

        elements.append(Paragraph("Mismatch Details", s["section_title"]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
        elements.append(Spacer(1, 4 * mm))

        sorted_m = sorted(
            self.data.mismatches,
            key=lambda m: Decimal(str(m.get("rupee_difference", 0))),
            reverse=True,
        )

        header = [
            Paragraph("Invoice No.", s["table_header"]),
            Paragraph("Supplier GSTIN", s["table_header"]),
            Paragraph("Type", s["table_header"]),
            Paragraph("Amount at Risk", s["table_header"]),
        ]
        rows = [header]

        for i, m in enumerate(sorted_m):
            mtype = str(m.get("mismatch_type", ""))
            type_label = MISMATCH_TYPE_LABELS.get(mtype, mtype)
            type_color = MISMATCH_TYPE_COLORS.get(mtype, DARK_GRAY)
            type_style = ParagraphStyle(
                f"ts_{i}", fontName="Helvetica-Bold", fontSize=7.5,
                textColor=type_color, alignment=TA_CENTER, leading=10,
            )
            gstin = str(m.get("supplier_gstin", ""))[:15]
            amount = Decimal(str(m.get("rupee_difference", 0)))
            rows.append([
                Paragraph(str(m.get("invoice_number", ""))[:22], s["table_cell"]),
                Paragraph(gstin, s["table_cell_center"]),
                Paragraph(type_label, type_style),
                Paragraph(_format_rupees(amount), s["table_cell_right"]),
            ])

        tbl = Table(rows, colWidths=[5.5 * cm, 5 * cm, 4.5 * cm, 6 * cm], repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_PURPLE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.25, LIGHT_GRAY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i in range(1, len(rows)):
            bg = WHITE if i % 2 == 1 else HexColor("#F8F7F3")
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
        tbl.setStyle(TableStyle(style_cmds))
        elements.append(tbl)
        elements.append(Spacer(1, 8 * mm))
        return elements

    def _section_explanations(self) -> list:
        s = self.styles
        elements: list = []
        if not self.data.mismatches:
            return elements

        elements.append(Paragraph("AI-Powered Explanations", s["section_title"]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
        elements.append(Spacer(1, 4 * mm))

        sorted_m = sorted(
            self.data.mismatches,
            key=lambda m: Decimal(str(m.get("rupee_difference", 0))),
            reverse=True,
        )

        for m in sorted_m:
            inv = str(m.get("invoice_number", ""))
            mtype = str(m.get("mismatch_type", ""))
            explanation = str(m.get("ai_explanation") or "No explanation available.")
            amount = Decimal(str(m.get("rupee_difference", 0)))
            type_label = MISMATCH_TYPE_LABELS.get(mtype, mtype)
            type_color = MISMATCH_TYPE_COLORS.get(mtype, DARK_GRAY)

            hdr_style = ParagraphStyle(
                "exp_hdr", fontName="Helvetica-Bold", fontSize=9, textColor=BRAND_PURPLE, leading=13,
            )
            sub_style = ParagraphStyle(
                "exp_sub", fontName="Helvetica", fontSize=8, textColor=type_color, leading=11,
            )

            hdr_row = Table(
                [[Paragraph(f"Invoice: {inv}", hdr_style), Paragraph(f"{type_label} · {_format_rupees(amount)}", sub_style)]],
                colWidths=[10 * cm, 11 * cm],
            )
            hdr_row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))

            exp_box = Table(
                [[Paragraph(explanation, s["explanation_box"])]],
                colWidths=[21 * cm],
            )
            exp_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))

            elements.append(KeepTogether([
                hdr_row,
                Spacer(1, 2 * mm),
                exp_box,
                Spacer(1, 5 * mm),
            ]))

        return elements

    def build(self) -> bytes:
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN + 10 * mm,
            bottomMargin=MARGIN + 12 * mm,
            title=f"GST Mismatch Report — {_format_month(self.data.scan_month)}",
            author="GSTSense",
        )
        story: list = []
        story.extend(self._section_business_details())
        story.extend(self._section_summary())
        story.extend(self._section_table())
        story.extend(self._section_explanations())
        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return buf.getvalue()


def generate_mismatch_report(report_data: ReportData) -> bytes:
    """Generate professional PDF mismatch report. Returns PDF as bytes."""
    logger.info(
        "pdf_generation_started",
        org=report_data.organization_name,
        scan_month=report_data.scan_month,
        mismatches=report_data.total_mismatches,
    )
    pdf_bytes = _ReportBuilder(report_data).build()
    logger.info("pdf_generation_complete", bytes=len(pdf_bytes))
    return pdf_bytes
