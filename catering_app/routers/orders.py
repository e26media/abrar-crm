from fastapi import APIRouter, Depends, Request, Form
from typing import Optional
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from datetime import datetime

from catering_app.database import get_db
from catering_app.models import Order, OrderItem, FoodItem, OrderStatusEnum
from catering_app.templating import templates
from catering_app.services.pricing import calculate_order_total

router = APIRouter(prefix="/orders", tags=["orders"])

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
    num_plates: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    ev_date = datetime.strptime(event_date, "%Y-%m-%d")
    new_order = Order(
        customer_name=customer_name,
        customer_phone=customer_phone,
        event_name=event_name,
        event_date=ev_date,
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
    
    calc_total = await calculate_order_total(db, id, order.num_plates)
    
    all_foods_result = await db.execute(
        select(FoodItem).options(selectinload(FoodItem.category)).where(FoodItem.is_active == True)
    )
    foods = all_foods_result.scalars().all()
    
    return templates.TemplateResponse(
        request=request, name="orders/detail.html", 
        context={"request": request, "id": id, "order": order, "calc_total": calc_total, "foods": foods}
    )

# htmx-partial
@router.get("/{id}/search_menu", response_class=HTMLResponse)
async def search_menu(request: Request, id: int, q: str = "", db: AsyncSession = Depends(get_db)):
    query = select(FoodItem).options(selectinload(FoodItem.category)).where(FoodItem.is_active == True)
    if q:
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
    
    # Recalculate totals and return the updated summary partial
    result = await db.execute(
        select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.food_item), 
            selectinload(Order.bill)
        ).where(Order.id == id)
    )
    order = result.scalar_one()
    calc_total = await calculate_order_total(db, id, order.num_plates)
    
    return templates.TemplateResponse(
        request=request, name="orders/_order_summary.html", 
        context={"request": request, "order": order, "calc_total": calc_total}
    )

# htmx-partial
@router.delete("/{id}/items/{item_id}", response_class=HTMLResponse)
async def remove_item_from_order(request: Request, id: int, item_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(OrderItem).where(OrderItem.id == item_id, OrderItem.order_id == id))
    await db.commit()
    
    result = await db.execute(
        select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.food_item), 
            selectinload(Order.bill)
        ).where(Order.id == id)
    )
    order = result.scalar_one()
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
        
    calc_total = await calculate_order_total(db, id, num_plates)
    
    return templates.TemplateResponse(
        request=request, name="orders/_order_summary.html", 
        context={"request": request, "order": order, "calc_total": calc_total}
    )

# htmx-partial
@router.post("/{id}/confirm", response_class=HTMLResponse)
async def confirm_order(request: Request, id: int, db: AsyncSession = Depends(get_db)):
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
        
    calc_total = await calculate_order_total(db, id, order.num_plates)
    
    return templates.TemplateResponse(
        request=request, name="orders/_order_summary.html", 
        context={"request": request, "order": order, "calc_total": calc_total}
    )

# htmx-partial
@router.post("/{id}/items/{item_id}/increment", response_class=HTMLResponse)
async def increment_item_quantity(request: Request, id: int, item_id: int, db: AsyncSession = Depends(get_db)):
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
    order = result.scalar_one()
    calc_total = await calculate_order_total(db, id, order.num_plates)
    return templates.TemplateResponse(request=request, name="orders/_order_summary.html", context={"request": request, "order": order, "calc_total": calc_total})

# htmx-partial
@router.post("/{id}/items/{item_id}/decrement", response_class=HTMLResponse)
async def decrement_item_quantity(request: Request, id: int, item_id: int, db: AsyncSession = Depends(get_db)):
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
    calc_total = await calculate_order_total(db, id, order.num_plates)
    return templates.TemplateResponse(request=request, name="orders/_order_summary.html", context={"request": request, "order": order, "calc_total": calc_total})
