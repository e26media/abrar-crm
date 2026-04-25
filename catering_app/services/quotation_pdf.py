"""
Generates a Quotation PDF matching the ABRAR reference image.
Updated to support multiple Sections (Menus) and separate logo/watermark.
"""

import os
import json
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

# Define the bronze/gold color from the brand template
BRONZE_COLOR = colors.Color(0.54, 0.37, 0.24) # Approx #8b5e3c

# ── Style helpers ─────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()

    doc_title = ParagraphStyle(
        "DocTitle", parent=base["Normal"],
        fontSize=15, alignment=TA_CENTER,
        fontName="Helvetica-Bold", spaceAfter=15,
        textColor=BRONZE_COLOR, underline=True
    )
    normal = ParagraphStyle(
        "Nrm", parent=base["Normal"],
        fontSize=10, leading=14,
    )
    section_heading = ParagraphStyle(
        "SecHeading", parent=base["Normal"],
        fontSize=11, leading=14, fontName="Helvetica-Bold",
        textColor=BRONZE_COLOR
    )
    cat_heading = ParagraphStyle(
        "CatHead", parent=base["Normal"],
        fontSize=10, leading=14, fontName="Helvetica-Bold",
        textColor=BRONZE_COLOR
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
        textColor=colors.white
    )
    total_val = ParagraphStyle(
        "TotalVal", parent=base["Normal"],
        fontSize=11, fontName="Helvetica-Bold", alignment=TA_CENTER,
        textColor=colors.white
    )

    return dict(
        doc_title=doc_title,
        normal=normal, section_heading=section_heading, cat_heading=cat_heading,
        sub_item=sub_item, standalone=standalone,
        amount_style=amount_style, total_label=total_label, total_val=total_val,
    )


def _fmt_amount(amount: int) -> str:
    return f"Rs. {amount:,}/-"

def draw_static_elements(canvas, doc):
    """Draws logo, watermark, and footer on every page."""
    canvas.saveState()
    
    # 1. Watermark (Centered)
    watermark_path = os.path.join("catering_app", "static", "watermark.png")
    if os.path.exists(watermark_path):
        w_width, w_height = 4.5*inch, 4.5*inch
        canvas.drawImage(
            watermark_path, 
            (A4[0] - w_width) / 2, 
            (A4[1] - w_height) / 2, 
            width=w_width, height=w_height, 
            mask='auto'
        )
        
    # 2. Logo (Top Centered)
    logo_path = os.path.join("catering_app", "static", "logo.png")
    if os.path.exists(logo_path):
        l_width = 3.5*inch
        l_height = 1.0*inch
        canvas.drawImage(
            logo_path, 
            (A4[0] - l_width) / 2, 
            A4[1] - l_height - 0.4*inch, 
            width=l_width, height=l_height, 
            mask='auto'
        )
        
    # 3. Footer (Address & Email)
    canvas.setStrokeColor(BRONZE_COLOR)
    canvas.setLineWidth(0.5)
    canvas.line(40, 70, A4[0] - 40, 70) # Horizontal line above footer
    
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.setFillColor(colors.black)
    footer_text1 = "Tilery Road, Mulihithlu, Bolar, Mangaluru 575 001, Ph: 91 9108659584, 91 9035341900"
    footer_text2 = "Email: abrarcaterers@gmail.com"
    
    canvas.drawCentredString(A4[0]/2, 55, footer_text1)
    canvas.drawCentredString(A4[0]/2, 42, footer_text2)
    
    canvas.restoreState()


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
    
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=40, rightMargin=40,
        topMargin=150, # Space for logo
        bottomMargin=100 # Space for footer
    )

    elements = []

    # ── 1. Title ─────────────────────────────────────────────────────────────
    elements.append(Paragraph("QUOTATION", S["doc_title"]))
    
    # ── 2. Info block ─────────────────────────────────────────────────────────
    date_str = datetime.now().strftime("%d/%m/%Y")
    fn_date_str = quotation.function_date.strftime("%d/%m/%Y")
    venue_str = quotation.venue or "-"
    customer_str = quotation.customer_name

    usable_w = page_w - 80 # Margins
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
    elements.append(Spacer(1, 15))

    # ── 3. Main description table ─────────────────────────────────────────────
    desc_w = usable_w * 0.72
    amt_w = usable_w * 0.28
    table_data = []

    # Header row
    table_data.append([
        Paragraph("<b>DESCRIPTION</b>", ParagraphStyle("DH", parent=S["normal"], alignment=TA_CENTER, fontName="Helvetica-Bold", textColor=colors.white)),
        Paragraph("<b>AMOUNT</b>", ParagraphStyle("AH", parent=S["normal"], alignment=TA_CENTER, fontName="Helvetica-Bold", textColor=colors.white)),
    ])

    grand_total = 0
    t_style = [
        ("BOX", (0, 0), (-1, -1), 1, BRONZE_COLOR),
        ("BACKGROUND", (0, 0), (-1, 0), BRONZE_COLOR),
        ("LINEBELOW", (0, 0), (-1, 0), 1, BRONZE_COLOR),
        ("LINEAFTER", (0, 0), (0, -1), 1, BRONZE_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    current_row = 1
    for section in sorted(quotation.sections, key=lambda x: x.display_order):
        section_start_row = current_row
        grand_total += section.amount
        
        # Section Heading row
        if section.name:
            table_data.append([
                Paragraph(f"<u>{section.name.upper()}</u>", S["section_heading"]),
                ""
            ])
            current_row += 1

        # Items in this section
        main_counter = 0
        sub_counter = 0
        
        for item in sorted(section.items, key=lambda x: x.display_order):
            if item.item_type == QuotationItemTypeEnum.category_item:
                if item.category_id and not item.food_item_id:
                    # Category header
                    main_counter += 1
                    sub_counter = 0
                    table_data.append([
                        Paragraph(f"{main_counter}.&nbsp;&nbsp;&nbsp;<b>{item.label.upper()}</b>", S["cat_heading"]),
                        ""
                    ])
                else:
                    # Sub item
                    sub_counter += 1
                    table_data.append([
                        Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{sub_counter}.&nbsp;&nbsp;&nbsp;{item.label}", S["sub_item"]),
                        ""
                    ])
            else:
                # Standalone Item
                main_counter += 1
                table_data.append([
                    Paragraph(f"{main_counter}.&nbsp;&nbsp;&nbsp;{item.label.upper()}", S["standalone"]),
                    ""
                ])
            current_row += 1

        section_end_row = current_row - 1
        
        # Span the amount cell for the whole section and center it vertically
        if section.amount:
            table_data[section_start_row][1] = Paragraph(_fmt_amount(section.amount), S["amount_style"])
            t_style.append(("SPAN", (1, section_start_row), (1, section_end_row)))
            t_style.append(("VALIGN", (1, section_start_row), (1, section_end_row), "MIDDLE"))
        
        # Add line below section to separate from the next one
        t_style.append(("LINEBELOW", (0, section_end_row), (-1, section_end_row), 1, BRONZE_COLOR))

    # Total row
    table_data.append([
        Paragraph("<b>TOTAL</b>", S["total_label"]),
        Paragraph(_fmt_amount(grand_total), S["total_val"]),
    ])
    t_style.append(("BACKGROUND", (0, -1), (-1, -1), BRONZE_COLOR))
    t_style.append(("VALIGN", (0, -1), (-1, -1), "MIDDLE"))
    t_style.append(("ALIGN", (1, -1), (1, -1), "CENTER"))

    main_table = Table(table_data, colWidths=[desc_w, amt_w], repeatRows=1)
    main_table.setStyle(TableStyle(t_style))
    elements.append(main_table)

    doc.build(elements, onFirstPage=draw_static_elements, onLaterPages=draw_static_elements)
    return f"/static/quotations/{filename}"
