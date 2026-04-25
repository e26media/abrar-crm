import json
from fastapi import APIRouter, Depends, Request
from datetime import datetime
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import os
from catering_app.database import get_db
from catering_app.config import settings
from catering_app.models import Order, Bill, BillItem, OrderStatusEnum
from catering_app.templating import templates
from catering_app.services.pricing import calculate_order_total
from catering_app.services.pdf_service import generate_bill_pdf
from catering_app import schemas

router = APIRouter(prefix="/bills", tags=["bills"])

@router.get("/new/{order_id}", response_class=HTMLResponse)
async def new_bill_form(request: Request, order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        return HTMLResponse("Order not found", status_code=404)
        
    # Check if bill already exists
    bill_result = await db.execute(select(Bill).where(Bill.order_id == order_id))
    bill = bill_result.scalar_one_or_none()
    
    if bill:
        # Redirect to bill detail or edit?
        # For now, let's just show the form with existing data if it's there
        pass

    # Pre-fill with order info
    initial_items = [
        {
            "item_date": order.event_date,
            "event_name": order.event_name,
            "venue": order.venue,
            "particulars": "Catering Service",
            "amount": 0.0,
            "discount_amount": 0.0,
            "display_order": 1
        }
    ]
    
    return templates.TemplateResponse(
        request=request, 
        name="bills/create.html", 
        context={
            "request": request, 
            "order": order, 
            "bill": bill,
            "initial_items": initial_items
        }
    )

@router.post("/save", response_class=HTMLResponse)
async def save_manual_bill(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    order_id = int(form_data.get("order_id"))
    customer_name = form_data.get("customer_name")
    advance_payment = max(0, int(float(form_data.get("advance_payment") or 0)))
    
    # Process items
    item_dates = form_data.getlist("item_date[]")
    event_names = form_data.getlist("event_name[]")
    venues = form_data.getlist("venue[]")
    particulars = form_data.getlist("particulars[]")
    amounts = form_data.getlist("amount[]")
    discounts = form_data.getlist("discount_amount[]")
    
    total_amount = 0
    bill_items_data = []
    
    for i in range(len(particulars)):
        # Skip row ONLY if it's completely empty
        if not particulars[i] and not event_names[i] and not venues[i]:
            continue
        
        # Validate mandatory fields
        if not item_dates[i] or not event_names[i] or not venues[i] or not particulars[i]:
            return HTMLResponse("<div class='bg-red-100 text-red-700 p-3 rounded mb-4'>Error: Date, Event, Venue, and Particulars are mandatory for all rows.</div>", status_code=400)
        
        amt = max(0, int(float(amounts[i] or 0)))
        dsc = max(0, int(float(discounts[i] or 0)))
        row_total = amt - dsc
        total_amount += row_total
        
        item_date = None
        if item_dates[i]:
            try:
                item_date = datetime.strptime(item_dates[i], "%Y-%m-%d")
            except:
                pass

        bill_items_data.append({
            "item_date": item_date,
            "event_name": event_names[i],
            "venue": venues[i],
            "particulars": particulars[i],
            "amount": amt,
            "discount_amount": dsc,
            "display_order": i + 1
        })

    # Update or create Bill
    from sqlalchemy.orm import selectinload
    bill_result = await db.execute(
        select(Bill).options(selectinload(Bill.items)).where(Bill.order_id == order_id)
    )
    bill = bill_result.scalar_one_or_none()
    
    if not bill:
        bill = Bill(order_id=order_id)
        db.add(bill)
    
    bill.customer_name = customer_name
    bill.grand_total = total_amount
    bill.advance_payment = advance_payment
    bill.balance_amount = max(0, total_amount - advance_payment)
    
    # Delete old items if updating
    from sqlalchemy import delete
    await db.execute(delete(BillItem).where(BillItem.bill_id == bill.id))
    
    # Add new items
    for item_data in bill_items_data:
        item = BillItem(bill_id=bill.id, **item_data)
        db.add(item)
    
    # Update order status
    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.status = OrderStatusEnum.billed
        
    await db.commit()
    
    # Re-fetch bill with items explicitly to avoid lazy loading in sync PDF generator
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Bill).options(selectinload(Bill.items)).where(Bill.id == bill.id)
    )
    bill = result.scalar_one()
    
    # Generate PDF
    os.makedirs(os.path.join("catering_app", "static", "bills"), exist_ok=True)
    pdf_rel_path = f"/static/bills/bill_{bill.id}.pdf"
    output_path = os.path.join(os.getcwd(), "catering_app", pdf_rel_path.lstrip("/"))
    
    from catering_app.services.pdf_service import generate_bill_pdf
    generate_bill_pdf(bill, output_path)
    
    bill.pdf_path = pdf_rel_path
    await db.commit()
    
    # Return a response that triggers the download event on the client side
    response = HTMLResponse("<div class='bg-green-50 text-green-700 p-3 rounded mb-4'>Bill saved! Downloading PDF...</div>")
    response.headers["HX-Trigger"] = json.dumps({"downloadPdf": {"url": f"/bills/{bill.id}/pdf"}})
    return response

@router.get("/add-row", response_class=HTMLResponse)
async def add_bill_item_row(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="bills/_item_row.html",
        context={"request": request, "index": int(request.query_params.get("index", 0))}
    )

@router.get("/{id}", response_class=HTMLResponse)
async def view_bill(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Bill).where(Bill.id == id))
    bill = result.scalar_one_or_none()
    
    return templates.TemplateResponse(request=request, name="bills/detail.html", context={"request": request, "bill": bill})

@router.get("/{id}/pdf")
async def download_bill_pdf(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Bill).where(Bill.id == id))
    bill = result.scalar_one_or_none()
    
    if not bill:
        return HTMLResponse("Bill record not found", status_code=404)
        
    # Translate relative /static/bills path to an absolute or correct path
    pdf_rel_path = bill.pdf_path if bill.pdf_path else f"/static/bills/bill_{id}.pdf"
    path = os.path.join(os.getcwd(), "catering_app", pdf_rel_path.lstrip("/"))
    
    # Re-generate PDF to ensure latest logic/branding is applied
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Bill).options(selectinload(Bill.items)).where(Bill.id == id)
    )
    bill = result.scalar_one_or_none()
    
    if bill:
        # Final validation check before generation
        for i, item in enumerate(bill.items):
            if not item.item_date or not item.event_name or not item.venue or not item.particulars:
                return HTMLResponse(f"Cannot generate PDF: Item #{i+1} ('{item.particulars}') is missing mandatory fields (Date, Event, or Venue). Please edit the bill, fill all fields, and click Save.", status_code=400)
                
        os.makedirs(os.path.dirname(path), exist_ok=True)
        generate_bill_pdf(bill, path)
    
    if not os.path.exists(path):
        return HTMLResponse(f"Failed to generate PDF at {path}", status_code=500)
        
    return FileResponse(path, filename=f"Bill_{id}.pdf")
