"""
Generates a Quotation PDF matching the ABRAR reference image.
Updated to support multiple Sections (Menus).
"""

import os
from datetime import datetime
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable, Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from catering_app.models import Quotation, QuotationItem, QuotationItemTypeEnum, QuotationSection


# ── Style helpers ─────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()

    brand = ParagraphStyle(
        "Brand", parent=base["Normal"],
        fontSize=30, leading=34,
        alignment=TA_CENTER, fontName="Helvetica-Bold",
    )
    address = ParagraphStyle(
        "Address", parent=base["Normal"],
        fontSize=9, alignment=TA_CENTER, spaceAfter=2,
    )
    doc_title = ParagraphStyle(
        "DocTitle", parent=base["Normal"],
        fontSize=13, alignment=TA_CENTER,
        fontName="Helvetica-Bold", spaceAfter=10,
    )
    normal = ParagraphStyle(
        "Nrm", parent=base["Normal"],
        fontSize=10, leading=14,
    )
    section_heading = ParagraphStyle(
        "SecHeading", parent=base["Normal"],
        fontSize=10, leading=14, fontName="Helvetica-Bold",
    )
    cat_heading = ParagraphStyle(
        "CatHead", parent=base["Normal"],
        fontSize=10, leading=14, fontName="Helvetica-Bold",
    )
    sub_item = ParagraphStyle(
        "SubItem", parent=base["Normal"],
        fontSize=10, leading=13, leftIndent=25,
    )
    standalone = ParagraphStyle(
        "Standalone", parent=base["Normal"],
        fontSize=10, leading=13, leftIndent=6,
    )
    amount_style = ParagraphStyle(
        "Amount", parent=base["Normal"],
        fontSize=10, leading=14, fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    total_label = ParagraphStyle(
        "TotalLbl", parent=base["Normal"],
        fontSize=11, fontName="Helvetica-Bold", alignment=TA_CENTER,
    )
    total_val = ParagraphStyle(
        "TotalVal", parent=base["Normal"],
        fontSize=11, fontName="Helvetica-Bold", alignment=TA_CENTER,
    )

    return dict(
        brand=brand, address=address, doc_title=doc_title,
        normal=normal, section_heading=section_heading, cat_heading=cat_heading,
        sub_item=sub_item, standalone=standalone,
        amount_style=amount_style, total_label=total_label, total_val=total_val,
    )


def _fmt_amount(amount: int) -> str:
    return f"Rs. {amount:,}/-"


# ── Main generator ────────────────────────────────────────────────────────────

async def generate_quotation_pdf(session: AsyncSession, quotation_id: int) -> str:
    # Fetch with sections and items
    result = await session.execute(
        select(Quotation)
        .options(
            selectinload(Quotation.sections)
            .selectinload(QuotationSection.items)
            .selectinload(QuotationItem.category),
            selectinload(Quotation.sections)
            .selectinload(QuotationSection.items)
            .selectinload(QuotationItem.food_item)
        )
        .where(Quotation.id == quotation_id)
    )
    quotation = result.scalar_one_or_none()
    if not quotation:
        raise ValueError(f"Quotation {quotation_id} not found")

    # Output path
    out_dir = os.path.join("catering_app", "static", "quotations")
    os.makedirs(out_dir, exist_ok=True)
    filename = f"quotation_{quotation_id}.pdf"
    filepath = os.path.join(out_dir, filename)

    S = _styles()
    page_w, page_h = A4
    margin = 35

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )

    elements = []

    # ── 1. Header ────────────────────────────────────────────────────────────
    logo_path = os.path.join("catering_app", "static", "logo.png")
    if os.path.exists(logo_path):
        # We can use a size that looks good, e.g., 1.5 inch width
        img = Image(logo_path, width=1.5*inch, height=1.5*inch)
        img.hAlign = 'CENTER'
        elements.append(img)
    else:
        elements.append(Paragraph("<b>ABRAR</b>", S["brand"]))
    elements.append(Paragraph(
        "Tilery Road, Mulihithliu, Bolar, Mangalore - 575001.&nbsp;&nbsp;"
        "MOB - 9108659584, 9035341900",
        S["address"],
    ))
    elements.append(Spacer(1, 6))

    # ── 2. Title ─────────────────────────────────────────────────────────────
    elements.append(Paragraph("<u><b>QUOTATION</b></u>", S["doc_title"]))
    elements.append(Spacer(1, 4))

    # ── 3. Info block ─────────────────────────────────────────────────────────
    date_str = datetime.now().strftime("%d/%m/%Y")
    fn_date_str = quotation.function_date.strftime("%d/%m/%Y")
    venue_str = quotation.venue or "-"
    customer_str = quotation.customer_name

    usable_w = page_w - 2 * margin
    left_w = usable_w * 0.65
    right_w = usable_w * 0.35

    info_data = [
        [Paragraph("<b>To,</b>", S["normal"]), Paragraph(f"<b>DATE :</b> {date_str}", S["normal"])],
        [Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Mr. {customer_str}", S["normal"]), ""],
    ]
    if quotation.customer_phone:
        info_data.append([Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Phone : {quotation.customer_phone}", S["normal"]), ""])
    
    info_data.extend([
        [Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Function Date : {fn_date_str}", S["normal"]), ""],
        [Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Venue : {venue_str}", S["normal"]), ""],
    ])

    info_table = Table(info_data, colWidths=[left_w, right_w])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # ── 4. Main description table ─────────────────────────────────────────────
    desc_w = usable_w * 0.72
    amt_w = usable_w * 0.28
    table_data = []

    # Header row
    table_data.append([
        Paragraph("<b>DESCRIPTION</b>", ParagraphStyle("DH", parent=S["normal"], alignment=TA_CENTER, fontName="Helvetica-Bold")),
        Paragraph("<b>AMOUNT</b>", ParagraphStyle("AH", parent=S["normal"], alignment=TA_CENTER, fontName="Helvetica-Bold")),
    ])

    grand_total = 0

    for section in sorted(quotation.sections, key=lambda x: x.display_order):
        grand_total += section.amount
        
        # Section Heading row
        if section.name:
            table_data.append([
                Paragraph(f"<u><b>{section.name.upper()}</b></u>", S["section_heading"]),
                "",
            ])

        # Items in this section
        main_counter = 0
        sub_counter = 0
        
        for item in sorted(section.items, key=lambda x: x.display_order):
            if item.amount and item.item_type == QuotationItemTypeEnum.standalone_item:
                if not section.amount:
                    grand_total += item.amount
                item_amt_str = _fmt_amount(item.amount)
            else:
                item_amt_str = ""

            if item.item_type == QuotationItemTypeEnum.category_item:
                if item.category_id and not item.food_item_id:
                    # Category header - top level numbering
                    main_counter += 1
                    sub_counter = 0 # Reset for the new category
                    table_data.append([
                        Paragraph(f"{main_counter}.&nbsp;&nbsp;&nbsp;<b>{item.label.upper()}</b>", S["cat_heading"]),
                        item_amt_str,
                    ])
                else:
                    # Sub item - nested numbering
                    sub_counter += 1
                    table_data.append([
                        Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{sub_counter}.&nbsp;&nbsp;&nbsp;{item.label}", S["sub_item"]),
                        item_amt_str,
                    ])
            else:
                # Standalone Item - top level numbering
                main_counter += 1
                table_data.append([
                    Paragraph(f"{main_counter}.&nbsp;&nbsp;&nbsp;{item.label.upper()}", S["standalone"]),
                    item_amt_str,
                ])

        # Section Amount row (if non-zero)
        if section.amount:
            table_data.append(["", Paragraph(_fmt_amount(section.amount), S["amount_style"])])

    # Total row
    table_data.append([
        Paragraph("<b>TOTAL</b>", S["total_label"]),
        Paragraph(_fmt_amount(grand_total), S["total_val"]),
    ])

    # Styling
    num_rows = len(table_data)
    t_style = [
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("LINEAFTER", (0, 0), (0, -1), 1, colors.black), # Vertical line between Description and Amount
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black), # Line below header
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black), # Line above Total
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    # Add lines between sections
    row_idx = 1 # Skip header
    sections = sorted(quotation.sections, key=lambda x: x.display_order)
    for i, section in enumerate(sections):
        if i > 0:
            # Add line ABOVE this section (effectively below the previous one)
            t_style.append(("LINEABOVE", (0, row_idx), (-1, row_idx), 0.5, colors.black))
            
        if section.name:
            row_idx += 1 # Section heading
        row_idx += len(section.items) # Items
        if section.amount:
            row_idx += 1 # Amount row

    main_table = Table(table_data, colWidths=[desc_w, amt_w], repeatRows=1)
    main_table.setStyle(TableStyle(t_style))
    elements.append(main_table)

    doc.build(elements)
    return f"/static/quotations/{filename}"
