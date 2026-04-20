from fastapi import APIRouter, Depends, Request, Form
from typing import Optional
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from datetime import datetime

from catering_app.database import get_db
from catering_app.models import Order, OrderItem, FoodItem, OrderStatusEnum, Bill, BillItem
from catering_app.templating import templates
from catering_app.services.pricing import calculate_order_total

router = APIRouter(prefix="/orders", tags=["orders"])

async def _apply_overrides(id: int, request: Request, db: AsyncSession):
    form_data = await request.form()
    
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == id)
    )
    order = result.scalar_one_or_none()
    if not order:
        return

    # 1. Update Order-level manual overrides
    m_total = form_data.get("manual_total")
    m_plate = form_data.get("manual_plate_rate")
    
    if m_total is not None and m_total != "":
        order.manual_total = float(m_total)
    if m_plate is not None and m_plate != "":
        order.manual_price_per_plate = float(m_plate)

    # 2. Update Item-level manual overrides
    # Pre-fetch items into a map for efficiency
    item_map = {item.id: item for item in order.items}
    
    for key, value in form_data.items():
        if value == "": continue
        
        if key.startswith("unit_price_"):
            try:
                item_id = int(key.replace("unit_price_", ""))
                if item_id in item_map:
                    item_map[item_id].unit_price = float(value)
            except ValueError: pass
        elif key.startswith("total_qty_"):
            try:
                item_id = int(key.replace("total_qty_", ""))
                if item_id in item_map:
                    target_total = float(value)
                    # We store quantity_per_plate. total = qpp * num_plates
                    item_map[item_id].quantity_per_plate = target_total / order.num_plates if order.num_plates > 0 else target_total
            except ValueError: pass
            
    await db.commit()
    return order

@router.get("/", response_class=HTMLResponse)
async def list_orders(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).order_by(Order.created_at.desc()))
    orders = result.scalars().all()
    return templates.TemplateResponse(request=request, name="orders/list.html", context={"request": request, "orders": orders})

@router.get("/new", response_class=HTMLResponse)
async def new_order_form(request: Request):
    return templates.TemplateResponse(request=request, name="orders/new.html", context={"request": request})

@router.post("/")
async def create_order(
    customer_name: str = Form(...),
    customer_phone: Optional[str] = Form(None),
    event_name: str = Form(...),
    event_date: str = Form(...),
    venue: Optional[str] = Form(None),
    num_plates: Optional[int] = Form(1),
    db: AsyncSession = Depends(get_db)
):
    ev_date = datetime.strptime(event_date, "%Y-%m-%d")
    new_order = Order(
        customer_name=customer_name,
        customer_phone=customer_phone,
        event_name=event_name,
        event_date=ev_date,
        venue=venue,
        num_plates=num_plates,
        status=OrderStatusEnum.draft
    )
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)
    return RedirectResponse(url=f"/orders/{new_order.id}", status_code=303)

@router.get("/{id}", response_class=HTMLResponse)
async def order_detail(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.food_item),
            selectinload(Order.bill)
        ).where(Order.id == id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Order not found")
        
    # Fetch Bill if exists
    bill_result = await db.execute(
        select(Bill).options(selectinload(Bill.items)).where(Bill.order_id == id)
    )
    bill = bill_result.scalar_one_or_none()

    # Pre-fill initial items if no bill exists
    initial_items = []
    if not bill:
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
        request=request, name="orders/detail.html", 
        context={
            "request": request, 
            "id": id, 
            "order": order, 
            "bill": bill,
            "initial_items": initial_items
        }
    )

# htmx-partial
@router.get("/{id}/search_menu", response_class=HTMLResponse)
async def search_menu(request: Request, id: int, q: str = "", db: AsyncSession = Depends(get_db)):
    if not q:
        foods = []
    else:
        query = select(FoodItem).options(selectinload(FoodItem.category)).where(FoodItem.is_active == True)
        query = query.where(FoodItem.name.ilike(f"%{q}%"))
        result = await db.execute(query)
        foods = result.scalars().all()
    
    return templates.TemplateResponse(
        request=request, name="orders/_food_list.html",
        context={"request": request, "id": id, "order": {"id": id}, "foods": foods}
    )

# htmx-partial
@router.put("/{id}/items/{item_id}", response_class=HTMLResponse)
async def update_item_quantity(
    request: Request, 
    id: int, 
    item_id: int, 
    quantity_per_plate: float = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(OrderItem).where(OrderItem.id == item_id, OrderItem.order_id == id))
    item = result.scalar_one_or_none()
    
    if item:
        item.quantity_per_plate = int(quantity_per_plate)
        await db.commit()
    
    result = await db.execute(select(Order).where(Order.id == id))
    order = result.scalar_one()
    calc_total = await calculate_order_total(db, id, order.num_plates)
    
    return templates.TemplateResponse(
        request=request, name="orders/_order_summary.html", 
        context={"request": request, "order": order, "calc_total": calc_total}
    )

# htmx-partial
@router.post("/{id}/items", response_class=HTMLResponse)
async def add_item_to_order(
    request: Request,
    id: int,
    food_item_id: int = Form(...),
    quantity_per_plate: float = Form(default=1.0),
    manual_total: Optional[float] = Form(None),
    manual_plate_rate: Optional[float] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    # Check if item already exists in this order
    existing_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == id, OrderItem.food_item_id == food_item_id)
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        existing.quantity_per_plate = int(existing.quantity_per_plate + quantity_per_plate)
    else:
        new_item = OrderItem(
            order_id=id,
            food_item_id=food_item_id,
            quantity_per_plate=int(quantity_per_plate),
            unit_price=0.0 # Will be recalculated
        )
        db.add(new_item)
        
    await db.commit()
    
    # Apply any other overrides from the form
    order = await _apply_overrides(id, request, db)
    
    # Recalculate totals and return the updated summary partial
    calc_total = await calculate_order_total(db, id, order.num_plates)
    
    return templates.TemplateResponse(
        request=request, name="orders/_order_summary.html", 
        context={"request": request, "order": order, "calc_total": calc_total}
    )

# htmx-partial
@router.delete("/{id}/items/{item_id}", response_class=HTMLResponse)
async def remove_item_from_order(
    request: Request, 
    id: int, 
    item_id: int, 
    manual_total: Optional[float] = Form(None),
    manual_plate_rate: Optional[float] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(delete(OrderItem).where(OrderItem.id == item_id, OrderItem.order_id == id))
    await db.commit()
    
    # Apply any other overrides from the form
    order = await _apply_overrides(id, request, db)
    
    calc_total = await calculate_order_total(db, id, order.num_plates)
    
    return templates.TemplateResponse(
        request=request, name="orders/_order_summary.html", 
        context={"request": request, "order": order, "calc_total": calc_total}
    )

# htmx-partial
@router.put("/{id}/plates", response_class=HTMLResponse)
async def update_plates(request: Request, id: int, num_plates: int = Form(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.food_item), 
            selectinload(Order.bill)
        ).where(Order.id == id)
    )
    order = result.scalar_one_or_none()
    if order:
        order.num_plates = num_plates
        await db.commit()
        # Apply any other overrides from the form
        order = await _apply_overrides(id, request, db)
        
    calc_total = await calculate_order_total(db, id, num_plates)
    
    return templates.TemplateResponse(
        request=request, name="orders/_order_summary.html", 
        context={"request": request, "order": order, "calc_total": calc_total}
    )

# htmx-partial
@router.post("/{id}/confirm", response_class=HTMLResponse)
async def confirm_order(
    request: Request, 
    id: int, 
    manual_total: Optional[float] = Form(None),
    manual_plate_rate: Optional[float] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.food_item), 
            selectinload(Order.bill)
        ).where(Order.id == id)
    )
    order = result.scalar_one_or_none()
    if order:
        order.status = OrderStatusEnum.confirmed
        await db.commit()
        # Apply any other overrides from the form
        order = await _apply_overrides(id, request, db)
        
    calc_total = await calculate_order_total(db, id, order.num_plates)
    
    return templates.TemplateResponse(
        request=request, name="orders/_order_summary.html", 
        context={"request": request, "order": order, "calc_total": calc_total}
    )

# htmx-partial
@router.post("/{id}/items/{item_id}/increment", response_class=HTMLResponse)
async def increment_item_quantity(
    request: Request, 
    id: int, 
    item_id: int, 
    manual_total: Optional[float] = Form(None),
    manual_plate_rate: Optional[float] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(OrderItem).where(OrderItem.id == item_id, OrderItem.order_id == id))
    item = result.scalar_one_or_none()
    if item:
        item.quantity_per_plate = int(item.quantity_per_plate) + 1
        await db.commit()
    
    result = await db.execute(
        select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.food_item), 
            selectinload(Order.bill)
        ).where(Order.id == id)
    )
    # Apply any other overrides from the form
    order = await _apply_overrides(id, request, db)
    calc_total = await calculate_order_total(db, id, order.num_plates)
    return templates.TemplateResponse(request=request, name="orders/_order_summary.html", context={"request": request, "order": order, "calc_total": calc_total})

# htmx-partial
@router.post("/{id}/items/{item_id}/decrement", response_class=HTMLResponse)
async def decrement_item_quantity(
    request: Request, 
    id: int, 
    item_id: int, 
    manual_total: Optional[float] = Form(None),
    manual_plate_rate: Optional[float] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(OrderItem).where(OrderItem.id == item_id, OrderItem.order_id == id))
    item = result.scalar_one_or_none()
    if item and item.quantity_per_plate > 1:
        item.quantity_per_plate = int(item.quantity_per_plate) - 1
        await db.commit()
    
    result = await db.execute(
        select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.food_item), 
            selectinload(Order.bill)
        ).where(Order.id == id)
    )
    order = result.scalar_one()
    # Apply any other overrides from the form
    order = await _apply_overrides(id, request, db)
    calc_total = await calculate_order_total(db, id, order.num_plates)
    return templates.TemplateResponse(request=request, name="orders/_order_summary.html", context={"request": request, "order": order, "calc_total": calc_total})
