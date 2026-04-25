import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime

# Define the bronze/gold color from the brand template
BRONZE_COLOR = colors.Color(0.54, 0.37, 0.24) # Approx #8b5e3c

def number_to_words(number):
    """Simple converter for Indian currency format (Lakhs, Crores)."""
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def convert_below_1000(n):
        if n == 0: return ""
        res = ""
        if n >= 100:
            res += units[n // 100] + " Hundred "
            n %= 100
        if n >= 20:
            res += tens[n // 10] + " "
            n %= 10
        if n >= 10:
            res += teens[n - 10] + " "
            n = 0
        if n > 0:
            res += units[n] + " "
        return res.strip()
    
    if number == 0: return "Zero"
    
    res = ""
    if number >= 10000000:
        res += convert_below_1000(number // 10000000) + " Crore "
        number %= 10000000
    if number >= 100000:
        res += convert_below_1000(number // 100000) + " Lakh "
        number %= 100000
    if number >= 1000:
        res += convert_below_1000(number // 1000) + " Thousand "
        number %= 1000
    res += convert_below_1000(number)
    
    return res.strip() + " Only"

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
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawCentredString(A4[0]/2, 42, footer_text2)
    
    canvas.restoreState()

def generate_bill_pdf(bill, output_path: str):
    doc = SimpleDocTemplate(
        output_path, 
        pagesize=A4, 
        rightMargin=40, 
        leftMargin=40, 
        topMargin=150, # Space for logo
        bottomMargin=100 # Space for footer
    )
    styles = getSampleStyleSheet()
    
    # Custom Styles
    est_bill_style = ParagraphStyle(
        'EstBill', parent=styles['Normal'], 
        fontSize=14, alignment=1, fontName='Helvetica-Bold', 
        textColor=BRONZE_COLOR, spaceAfter=20, underline=True
    )
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=11, leading=14)
    table_header_style = ParagraphStyle(
        'TableHeader', parent=styles['Normal'], 
        fontSize=10, fontName='Helvetica-Bold', alignment=1,
        textColor=colors.white
    )
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontSize=10, leading=12)
    right_style = ParagraphStyle('RightStyle', parent=styles['Normal'], fontSize=10, leading=12, alignment=2)
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=10, leading=12, fontName='Helvetica-Bold')
    right_bold_style = ParagraphStyle('RightBold', parent=styles['Normal'], fontSize=10, leading=12, fontName='Helvetica-Bold', alignment=2)
    bronze_bold_style = ParagraphStyle('BronzeBold', parent=bold_style, textColor=BRONZE_COLOR)

    elements = []

    # Title
    elements.append(Paragraph("ESTIMATED BILL", est_bill_style))
    
    # Bill To & Date
    bill_date = bill.generated_at.strftime("%d/%m/%Y")
    header_table = Table([
        [Paragraph(f"<b>To,</b><br/>&nbsp;&nbsp;&nbsp;&nbsp;{bill.customer_name or ''}", header_style), 
         Paragraph(f"DATE : {bill_date}", ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=11, alignment=2, fontName='Helvetica-Bold'))]
    ], colWidths=[4.2*inch, 2*inch])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*inch))

    # Table Header
    table_data = [
        [Paragraph("Sl No.", table_header_style), 
         Paragraph("DATE", table_header_style), 
         Paragraph("EVENT", table_header_style), 
         Paragraph("VENUE", table_header_style), 
         Paragraph("PARTICULARS", table_header_style), 
         Paragraph("AMOUNT", table_header_style)]
    ]

    # Grouping logic
    groups = {}
    for item in bill.items:
        item_date_str = item.item_date.strftime("%d/%m/%y") if item.item_date else bill.generated_at.strftime("%d/%m/%y")
        key = (item_date_str, item.venue or "", item.event_name or "")
        if key not in groups:
            groups[key] = []
        groups[key].append(item)
    
    total_amount_sum = 0
    
    for si, (key, items) in enumerate(groups.items(), 1):
        date_str, venue_str, event_str = key
        group_discount = 0
        
        for i, item in enumerate(items):
            row = [
                Paragraph(str(si) if i == 0 else "", normal_style),
                Paragraph(date_str if i == 0 else "", normal_style),
                Paragraph(event_str if i == 0 else "", bronze_bold_style),
                Paragraph(venue_str if i == 0 else "", normal_style),
                Paragraph(item.particulars or "", normal_style),
                Paragraph(f"{item.amount:,.0f}" if item.amount else "0", right_style)
            ]
            table_data.append(row)
            total_amount_sum += item.amount
            group_discount += (item.discount_amount or 0)
            
        if group_discount > 0:
            table_data.append([
                "", "", "", "", 
                Paragraph("<b>Discount Amount</b>", bold_style), 
                Paragraph(f"-{int(group_discount):,}", right_bold_style)
            ])
            total_amount_sum -= group_discount

    # Footers
    table_data.append(["", "", "", "", Paragraph("<b>TOTAL</b>", bronze_bold_style), Paragraph(f"<b>{int(total_amount_sum):,}</b>", right_bold_style)])
    table_data.append(["", "", "", "", Paragraph("<b>ADVANCE RECEIVED</b>", bold_style), Paragraph(f"<b>{int(bill.advance_payment):,}</b>", right_bold_style)])
    
    balance = max(0, total_amount_sum - bill.advance_payment)
    table_data.append(["", "", "", "", Paragraph("<b>TOTAL BALANCE AMOUNT</b>", ParagraphStyle('LargeBold', parent=bronze_bold_style, fontSize=11)), Paragraph(f"<b>{int(balance):,}</b>", ParagraphStyle('LargeBoldRight', parent=right_bold_style, fontSize=11))])
    
    # Amount in words
    words = number_to_words(int(balance))
    table_data.append(["", Paragraph(f"(Rupees {words})", normal_style), "", "", "", ""])

    # Table Styling
    col_widths = [0.5*inch, 0.8*inch, 1.1*inch, 1.1*inch, 2.0*inch, 1.0*inch]
    main_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    main_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, BRONZE_COLOR),
        ('BACKGROUND', (0,0), (-1,0), BRONZE_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('SPAN', (1,-1), (5,-1)),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    
    elements.append(main_table)
    elements.append(Spacer(1, 0.4*inch))
    
    elements.append(Paragraph("Yours faithfully,", ParagraphStyle('Right', parent=styles['Normal'], alignment=2, rightIndent=20)))
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph(f"<b>For <font color='#8b5e3c'>ABRAR Catering Service</font></b>", ParagraphStyle('RightBold', parent=styles['Normal'], alignment=2, rightIndent=20)))

    # Build PDF with static elements drawer
    doc.build(elements, onFirstPage=draw_static_elements, onLaterPages=draw_static_elements)
