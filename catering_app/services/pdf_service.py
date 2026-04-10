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
            selectinload(Bill.order).selectinload(Order.items).selectinload(OrderItem.food_item).selectinload(FoodItem.category)
        )
        .where(Bill.id == bill_id)
    )
    bill = result.scalar_one_or_none()

    if not bill:
        raise ValueError(f"Bill {bill_id} not found")

    # Fetch order items separately since earlier query might be tricky
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
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []

    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        alignment=1, # Center
        spaceAfter=15,
        textColor=colors.HexColor('#2c3e50')
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=5
    )

    # Header
    elements.append(Paragraph(f"<b>{settings.app_name}</b>", title_style))
    elements.append(Paragraph("Excellent Catering For Your Events", ParagraphStyle('TagLine', parent=styles['Normal'], alignment=1, spaceAfter=20)))

    # Bill Info
    data_info = [
        [Paragraph("<b>Bill No:</b>", header_style), f"BILL-{bill.id}", Paragraph("<b>Date:</b>", header_style), bill.generated_at.strftime("%Y-%m-%d %H:%M")],
        [Paragraph("<b>Customer Name:</b>", header_style), order.customer_name, Paragraph("<b>Event Date:</b>", header_style), order.event_date.strftime("%Y-%m-%d")],
        [Paragraph("<b>Phone:</b>", header_style), order.customer_phone, Paragraph("<b>Event Name:</b>", header_style), order.event_name],
        [Paragraph("<b>Number of Plates:</b>", header_style), str(order.num_plates), "", ""]
    ]
    
    table_info = Table(data_info, colWidths=[100, 150, 80, 150])
    table_info.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(table_info)
    elements.append(Spacer(1, 20))

    # Items Table
    table_data = [
        ['#', 'Item Name', 'Category', 'Unit', 'Qty / Plate', 'Total Qty', 'Unit Price', 'Line Total']
    ]
    
    for i, item in enumerate(order_items, 1):
        food = item.food_item
        cat_name = food.category.name if food.category else "Unknown"
        total_qty = item.quantity_per_plate * order.num_plates
        
        row = [
            str(i),
            food.name,
            cat_name,
            food.unit.value,
            f"{item.quantity_per_plate:.2f}",
            f"{total_qty:.2f}",
            f"Rs {item.unit_price:.2f}",
            f"Rs {item.calculated_total:.2f}"
        ]
        table_data.append(row)

    # Styling the items table
    t = Table(table_data, colWidths=[30, 100, 60, 50, 70, 60, 70, 80])
    
    # Base style
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 11),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 10),
        ('ALIGN', (6,1), (-1,-1), 'RIGHT'), # Prices right aligned
        ('GRID', (0,0), (-1,-1), 1, colors.white),
    ]

    # Highlight non-veg
    for i, item in enumerate(order_items, 1):
        food = item.food_item
        cat_name = food.category.name if food.category else "Unknown"
        if cat_name.lower() == "non-veg" or cat_name.lower() == "non veg":
            t_style.append(('TEXTCOLOR', (1,i), (1,i), colors.red))

    t.setStyle(TableStyle(t_style))
    elements.append(t)
    elements.append(Spacer(1, 20))

    # Totals Table
    price_per_plate = bill.grand_total / order.num_plates if order.num_plates > 0 else 0.0
    totals_data = [
        ['', '', 'Subtotal:', f"Rs {bill.subtotal:.2f}"],
        ['', '', f"Tax ({bill.tax_percent}%):", f"Rs {bill.tax_amount:.2f}"],
        ['', '', 'Grand Total:', f"Rs {bill.grand_total:.2f}"],
        ['', '', 'Price Per Plate (Incl. Tax):', f"Rs {price_per_plate:.2f}"]
    ]
    totals_table = Table(totals_data, colWidths=[200, 100, 100, 120])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('FONTNAME', (2,2), (-1,2), 'Helvetica-Bold'),
        ('FONTSIZE', (2,2), (-1,2), 12),
        ('TEXTCOLOR', (2,2), (-1,2), colors.HexColor('#27ae60')),
        ('TOPPADDING', (2,2), (-1,2), 10),
        ('LINEABOVE', (2,2), (-1,2), 1, colors.black),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 40))

    # Footer
    elements.append(Paragraph("<b>Thank you for your business!</b>", ParagraphStyle('Footer', parent=styles['Normal'], alignment=1)))
    
    doc.build(elements)

    # Save to db
    bill.pdf_path = f"/static/bills/{pdf_filename}"
    session.add(bill)
    await session.commit()

    return bill.pdf_path
