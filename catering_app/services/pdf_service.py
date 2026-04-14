import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from catering_app.models import Bill, Order, OrderItem, FoodItem
from catering_app.config import settings

async def generate_bill_pdf(session: AsyncSession, bill_id: int) -> str:
    # Fetch Bill with related Order and OrderItems (with FoodItem)
    result = await session.execute(
        select(Bill)
        .options(
            selectinload(Bill.order).selectinload(Order.items).selectinload(OrderItem.food_item)
        )
        .where(Bill.id == bill_id)
    )
    bill = result.scalar_one_or_none()

    if not bill:
        raise ValueError(f"Bill {bill_id} not found")

    order = bill.order
    items_result = await session.execute(
        select(OrderItem)
        .options(selectinload(OrderItem.food_item))
        .where(OrderItem.order_id == order.id)
    )
    order_items = items_result.scalars().all()

    # Ensure static/bills directory exists
    bills_dir = os.path.join("catering_app", "static", "bills")
    os.makedirs(bills_dir, exist_ok=True)
    
    pdf_filename = f"bill_{bill.id}.pdf"
    pdf_path = os.path.join(bills_dir, pdf_filename)

    # ------------------ PDF Generation (ReportLab) ------------------
    from reportlab.lib.units import inch
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []

    styles = getSampleStyleSheet()
    
    # Custom Styles based on the image
    brand_style = ParagraphStyle(
        'BrandStyle',
        parent=styles['Normal'],
        fontSize=36,
        leading=40,
        alignment=1, # Center
        fontName='Helvetica-Bold',
        spaceAfter=2
    )
    
    address_style = ParagraphStyle(
        'AddressStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=1, # Center
        spaceAfter=2
    )
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Normal'],
        fontSize=14,
        alignment=1, # Center
        fontName='Helvetica-Bold',
        spaceAfter=20,
        underline=True
    )
    
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=11,
        leading=16
    )

    # 1. Branding Header
    elements.append(Paragraph("<b>ABRAR</b>", brand_style))
    elements.append(Paragraph("Tilery Road, Mulihithliu, Bolar, Mangalore - 575001.  MOB - 9108659584, 9035341900", address_style))
    elements.append(Spacer(1, 10))
    
    # 2. Title
    elements.append(Paragraph("<u><b>ESTIMATED BILL</b></u>", title_style))
    
    # 3. Info Section (To, DATE, M/s, etc.)
    # Using a table for alignment
    date_str = bill.generated_at.strftime("%d/%m/%Y")
    info_data = [
        [Paragraph("<b>To,</b>", normal_style), "", "", Paragraph(f"<b>DATE :</b> {date_str}", normal_style)],
        ["", Paragraph("M/s", normal_style), f": {order.customer_name}", ""],
        ["", Paragraph("Function Date", normal_style), f": {order.event_date.strftime('%d/%m/%Y')}", ""],
        ["", Paragraph("Venue", normal_style), f": {order.venue or ''}", ""],
    ]
    
    info_table = Table(info_data, colWidths=[0.5*inch, 1.2*inch, 2.5*inch, 1.5*inch])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))

    # 4. Items Table
    # Columns: Sl No., PARTICULARS, AMOUNT
    table_data = [
        [Paragraph("<b>Sl No.</b>", normal_style), Paragraph("<b>PARTICULARS</b>", normal_style), Paragraph("<b>AMOUNT</b>", normal_style)]
    ]
    
    for i, item in enumerate(order_items, 1):
        table_data.append([
            str(i),
            item.food_item.name,
            f"{item.calculated_total:,.2f}"
        ])
    
    # Add empty rows to match look if needed (optional, but image shows space)
    # for _ in range(max(0, 6 - len(order_items))):
    #     table_data.append(["", "", ""])

    # Total row
    table_data.append([
        "",
        Paragraph("<b>TOTAL</b>", ParagraphStyle('TotalLabel', parent=normal_style, alignment=1)),
        f"{bill.grand_total:,.2f}"
    ])

    # Styling the main table
    col_widths = [0.6*inch, 3.8*inch, 1.2*inch]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    t_style = [
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,-1), 'CENTER'), # Sl No. center
        ('ALIGN', (1,0), (1,0), 'CENTER'), # PARTICULARS header center
        ('ALIGN', (2,0), (2,-1), 'CENTER'), # AMOUNT center (as per image)
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (1,-1), (1,-1), 'Helvetica-Bold'), # TOTAL label bold
        ('LEFTPADDING', (1,1), (1,-2), 10), # Padding for item names
    ]
    
    t.setStyle(TableStyle(t_style))
    elements.append(t)
    elements.append(Spacer(1, 40))

    # 5. Footer Signature
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=11,
        alignment=2, # Right
        leading=14
    )
    
    elements.append(Paragraph("<i>Yours faithfully,</i>", footer_style))
    elements.append(Paragraph("For <b>ABRAR</b>", footer_style))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<b>MOHAMMED ASHFAQ</b>", footer_style))
    elements.append(Paragraph("(Partner)", footer_style))
    
    doc.build(elements)

    # Save to db
    bill.pdf_path = f"/static/bills/{pdf_filename}"
    session.add(bill)
    await session.commit()

    return bill.pdf_path
