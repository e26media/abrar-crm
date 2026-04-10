from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import os
from catering_app.database import get_db
from catering_app.config import settings
from catering_app.models import Order, Bill, OrderStatusEnum
from catering_app.templating import templates
from catering_app.services.pricing import calculate_order_total
from catering_app.services.pdf_service import generate_bill_pdf

router = APIRouter(prefix="/bills", tags=["bills"])

@router.post("/{order_id}", response_class=HTMLResponse)
async def generate_bill(request: Request, order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        return HTMLResponse("Order not found", status_code=404)
        
    calc_total = await calculate_order_total(db, order_id, order.num_plates)
    
    # Check if bill exists
    bill_result = await db.execute(select(Bill).where(Bill.order_id == order_id))
    bill = bill_result.scalar_one_or_none()
    
    if not bill:
        bill = Bill(
            order_id=order_id,
            subtotal=calc_total.subtotal,
            tax_percent=settings.tax_percent,
            tax_amount=calc_total.tax_amount,
            grand_total=calc_total.grand_total
        )
        db.add(bill)
        
    order.status = OrderStatusEnum.billed
    await db.commit()
    await db.refresh(bill)
    
    # Generate PDF
    pdf_path = await generate_bill_pdf(db, bill.id)
    
    # In HTMX context we want to return a success message or download link
    # This will replace the "Generate Bill" button
    return templates.TemplateResponse(request=request, name="bills/_bill_generated.html", context={"request": request, "bill": bill})

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
    
    # If the physical file is missing, re-generate it!
    if not os.path.exists(path):
        await generate_bill_pdf(db, id)
        # Verify it was created
        if not os.path.exists(path):
            return HTMLResponse(f"Failed to generate PDF at {path}", status_code=500)
        
    return FileResponse(path, filename=f"Bill_{id}.pdf")
