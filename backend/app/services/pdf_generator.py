import re
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


def generate_notice_reply_pdf(
    notice_number: str,
    organization_name: str,
    gstin: str,
    draft_reply_text: str,
    icai_membership_number: str,
    generated_at: datetime,
    warnings: Optional[list[str]] = None,
) -> bytes:
    """Generate PDF of notice reply draft with non-removable legal disclaimer."""
    from app.services.notice_drafter import LEGAL_DISCLAIMER

    NOTICE_RED = HexColor("#CC0000")
    AMBER_BG = HexColor("#FFF8E1")
    AMBER_BORDER = HexColor("#FF8F00")
    PLACEHOLDER_COLOR = HexColor("#E65100")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 14 * mm,
        bottomMargin=MARGIN + 20 * mm,
        title=f"GSTSense Notice Reply Draft — {notice_number}",
        author="GSTSense",
    )

    disclaimer_style = ParagraphStyle(
        "disclaimer",
        fontName="Helvetica",
        fontSize=7,
        textColor=NOTICE_RED,
        leading=10,
        alignment=TA_CENTER,
    )
    header_warning_style = ParagraphStyle(
        "header_warning",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=NOTICE_RED,
        leading=12,
        alignment=TA_RIGHT,
    )
    meta_label_style = ParagraphStyle(
        "meta_label",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=DARK_GRAY,
        leading=11,
    )
    meta_value_style = ParagraphStyle(
        "meta_value",
        fontName="Helvetica",
        fontSize=8,
        textColor=DARK_GRAY,
        leading=11,
    )
    section_style = ParagraphStyle(
        "notice_section",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=BRAND_PURPLE,
        leading=14,
        spaceBefore=6,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "notice_body",
        fontName="Helvetica",
        fontSize=9,
        textColor=DARK_GRAY,
        leading=13,
        spaceAfter=4,
    )
    placeholder_style = ParagraphStyle(
        "placeholder",
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=PLACEHOLDER_COLOR,
        leading=13,
    )
    warning_style = ParagraphStyle(
        "warning_item",
        fontName="Helvetica",
        fontSize=8,
        textColor=HexColor("#5D4037"),
        leading=11,
    )

    def _on_notice_page(canvas, doc):  # type: ignore[no-untyped-def]
        canvas.saveState()

        # ---- Header ----
        header_y = PAGE_H - MARGIN + 2 * mm
        canvas.setFont("Helvetica-Bold", 13)
        canvas.setFillColor(BRAND_PURPLE)
        canvas.drawString(MARGIN, header_y, "GSTSense")

        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(NOTICE_RED)
        canvas.drawRightString(
            PAGE_W - MARGIN,
            header_y,
            "Notice Reply Draft — NOT FOR DIRECT SUBMISSION",
        )

        canvas.setStrokeColor(NOTICE_RED)
        canvas.setLineWidth(1.0)
        canvas.line(MARGIN, header_y - 4 * mm, PAGE_W - MARGIN, header_y - 4 * mm)

        # ---- Footer disclaimer (non-removable) ----
        footer_top = MARGIN - 2 * mm
        box_h = 17 * mm
        canvas.setStrokeColor(NOTICE_RED)
        canvas.setLineWidth(0.8)
        canvas.rect(MARGIN, footer_top - box_h, PAGE_W - 2 * MARGIN, box_h)

        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(NOTICE_RED)
        canvas.drawString(MARGIN + 2 * mm, footer_top - 4 * mm, "⚠ LEGAL DISCLAIMER")

        # Wrap disclaimer text manually into the box
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(DARK_GRAY)
        disclaimer_words = LEGAL_DISCLAIMER.split()
        line = ""
        y_pos = footer_top - 8 * mm
        max_w = PAGE_W - 2 * MARGIN - 4 * mm
        for word in disclaimer_words:
            test_line = f"{line} {word}".strip()
            if canvas.stringWidth(test_line, "Helvetica", 6.5) < max_w:
                line = test_line
            else:
                canvas.drawString(MARGIN + 2 * mm, y_pos, line)
                y_pos -= 3.5 * mm
                line = word
        if line:
            canvas.drawString(MARGIN + 2 * mm, y_pos, line)

        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(DARK_GRAY)
        canvas.drawCentredString(PAGE_W / 2, footer_top - box_h - 3 * mm, f"Page {doc.page}")

        canvas.restoreState()

    story: list = []

    # ---- Meta block ----
    generated_str = generated_at.strftime("%d %B %Y, %I:%M %p")
    left_meta = [
        [Paragraph("Reference Notice:", meta_label_style), Paragraph(notice_number, meta_value_style)],
        [Paragraph("Taxpayer:", meta_label_style), Paragraph(organization_name, meta_value_style)],
        [Paragraph("GSTIN:", meta_label_style), Paragraph(gstin, meta_value_style)],
    ]
    right_meta = [
        [Paragraph("Generated:", meta_label_style), Paragraph(generated_str, meta_value_style)],
        [Paragraph("Prepared by CA:", meta_label_style), Paragraph(icai_membership_number, meta_value_style)],
        [Paragraph("Status:", meta_label_style), Paragraph("DRAFT — REQUIRES CA REVIEW", ParagraphStyle(
            "status", fontName="Helvetica-Bold", fontSize=8, textColor=NOTICE_RED, leading=11,
        ))],
    ]
    cell_s = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ])
    left_tbl = Table(left_meta, colWidths=[3.5 * cm, 7 * cm])
    left_tbl.setStyle(cell_s)
    right_tbl = Table(right_meta, colWidths=[3.5 * cm, 7 * cm])
    right_tbl.setStyle(cell_s)
    meta_row = Table([[left_tbl, right_tbl]], colWidths=[11 * cm, 10 * cm])
    meta_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_row)
    story.append(Spacer(1, 4 * mm))

    # ---- Warnings box ----
    if warnings:
        warn_rows = [[Paragraph("⚠ AI Verification Warnings:", ParagraphStyle(
            "warn_hdr", fontName="Helvetica-Bold", fontSize=9, textColor=HexColor("#5D4037"), leading=12,
        ))]]
        for w in warnings:
            warn_rows.append([Paragraph(f"• {w}", warning_style)])
        warn_tbl = Table(warn_rows, colWidths=[PAGE_W - 2 * MARGIN])
        warn_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), AMBER_BG),
            ("BOX", (0, 0), (-1, -1), 0.8, AMBER_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(warn_tbl)
        story.append(Spacer(1, 4 * mm))

    # ---- Draft content ----
    story.append(HRFlowable(width="100%", thickness=0.5, color=NOTICE_RED))
    story.append(Spacer(1, 3 * mm))

    for line in draft_reply_text.splitlines():
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 2 * mm))
            continue
        # Detect section headings (numbered or ALL CAPS short lines)
        if re.match(r"^\d+\.", stripped) or (stripped.isupper() and len(stripped) < 80):
            story.append(Paragraph(stripped, section_style))
        elif "[PLACEHOLDER" in stripped or "[placeholder" in stripped.lower():
            story.append(Paragraph(stripped, placeholder_style))
        else:
            story.append(Paragraph(stripped, body_style))

    story.append(Spacer(1, 8 * mm))

    # ---- Signature block ----
    sig_data = [
        [Paragraph("Signature:", meta_label_style), Paragraph("_" * 35, meta_value_style)],
        [Paragraph("Name:", meta_label_style), Paragraph("_" * 35, meta_value_style)],
        [Paragraph("ICAI Membership No:", meta_label_style), Paragraph("_" * 25, meta_value_style)],
        [Paragraph("Date:", meta_label_style), Paragraph("_" * 25, meta_value_style)],
    ]
    sig_tbl = Table(sig_data, colWidths=[4.5 * cm, 10 * cm])
    sig_tbl.setStyle(cell_s)
    story.append(sig_tbl)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "This reply must be signed by the authorized representative before submission to the GST portal.",
        ParagraphStyle("sig_note", fontName="Helvetica-Oblique", fontSize=8, textColor=NOTICE_RED, leading=11),
    ))

    doc.build(story, onFirstPage=_on_notice_page, onLaterPages=_on_notice_page)
    logger.info("notice_pdf_generated", notice_number=notice_number, bytes=buf.tell())
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


def generate_bulk_ca_report(
    firm_name: str,
    primary_ca_name: str,
    icai_membership_number: str,
    city: str,
    state: str,
    total_clients: int,
    total_earnings: float,
    clients: list[dict],
    commissions: list[dict],
    generated_at: datetime,
) -> bytes:
    """Generate a bulk CA firm report PDF. Returns PDF bytes."""
    styles = _build_styles()
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN + 1 * cm,
    )

    story = []

    # Header
    story.append(Paragraph(firm_name, styles["section_title"]))
    story.append(Paragraph(
        f"{primary_ca_name} · ICAI {icai_membership_number} · {city}, {state}",
        styles["label"],
    ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_PURPLE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Client Portfolio Report — Generated {generated_at.strftime('%d %B %Y %H:%M UTC')}",
        styles["body"],
    ))
    story.append(Spacer(1, 12))

    # Summary row
    summary_data = [
        ["Total Clients", "Active Clients", "Total Earnings"],
        [
            str(total_clients),
            str(sum(1 for c in clients)),
            f"₹{total_earnings:,.2f}",
        ],
    ]
    summary_table = Table(
        summary_data,
        colWidths=[(PAGE_W - 2 * MARGIN) / 3] * 3,
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # Clients table
    if clients:
        story.append(Paragraph("Client Organisations", styles["section_title"]))
        story.append(Spacer(1, 6))
        col_w = (PAGE_W - 2 * MARGIN) / 4
        header_row = [
            Paragraph("<b>Organisation</b>", styles["table_header"]),
            Paragraph("<b>GSTIN</b>", styles["table_header"]),
            Paragraph("<b>Commission Rate</b>", styles["table_header"]),
            Paragraph("<b>Added On</b>", styles["table_header"]),
        ]
        rows = [header_row]
        for c in clients:
            rows.append([
                Paragraph(c["name"], styles["table_cell"]),
                Paragraph(c["gstin"], styles["table_cell"]),
                Paragraph(f"{c['commission_rate'] * 100:.1f}%", styles["table_cell"]),
                Paragraph(c["added_on"], styles["table_cell"]),
            ])
        t = Table(rows, colWidths=[col_w * 1.6, col_w * 1.2, col_w * 0.6, col_w * 0.6])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_PURPLE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 16))

    # Commissions table
    if commissions:
        story.append(Paragraph("Referral Commissions", styles["section_title"]))
        story.append(Spacer(1, 6))
        col_w = (PAGE_W - 2 * MARGIN) / 5
        header_row = [
            Paragraph("<b>Organisation</b>", styles["table_header"]),
            Paragraph("<b>Amount</b>", styles["table_header"]),
            Paragraph("<b>Rate</b>", styles["table_header"]),
            Paragraph("<b>Status</b>", styles["table_header"]),
            Paragraph("<b>Date</b>", styles["table_header"]),
        ]
        rows = [header_row]
        for c in commissions:
            status_color = BRAND_TEAL if c["status"] == "paid" else (AMBER if c["status"] == "pending" else DARK_GRAY)
            rows.append([
                Paragraph(c["org_name"][:30], styles["table_cell"]),
                Paragraph(f"₹{c['amount']:,.2f}", styles["table_cell"]),
                Paragraph(f"{c['rate'] * 100:.1f}%", styles["table_cell"]),
                Paragraph(c["status"].upper(), ParagraphStyle(
                    "status_cell",
                    parent=styles["table_cell"],
                    textColor=status_color,
                    fontName="Helvetica-Bold",
                )),
                Paragraph(c["date"], styles["table_cell"]),
            ])
        t = Table(rows, colWidths=[col_w * 1.5, col_w * 0.8, col_w * 0.6, col_w * 0.7, col_w * 0.7] if False else [col_w] * 5)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_PURPLE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

    doc.build(story)
    return buf.getvalue()
