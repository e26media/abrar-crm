from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from catering_app.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from catering_app.database import get_db
from fastapi import Depends
from catering_app.models import Order, Bill, OrderStatusEnum, FoodItem

from catering_app.routers import items, orders, bills

app = FastAPI(title=settings.app_name)

app.include_router(items.router)
app.include_router(orders.router)
app.include_router(bills.router)

# Will be mounted fully when directories exist
try:
    app.mount("/static", StaticFiles(directory="catering_app/static"), name="static")
except RuntimeError:
    pass # In case directory is not created yet

from catering_app.templating import templates

@app.get("/")
async def root(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. Total Orders
    total_orders_res = await db.execute(select(func.count(Order.id)))
    total_orders = total_orders_res.scalar() or 0
    
    # 2. Pending Orders (Draft + Confirmed)
    pending_orders_res = await db.execute(
        select(func.count(Order.id)).where(Order.status.in_([OrderStatusEnum.draft, OrderStatusEnum.confirmed]))
    )
    pending_orders = pending_orders_res.scalar() or 0
    
    # 3. Completed (Billed)
    completed_orders_res = await db.execute(
        select(func.count(Order.id)).where(Order.status == OrderStatusEnum.billed)
    )
    completed_orders = completed_orders_res.scalar() or 0
    
    # 4. Total Revenue
    revenue_res = await db.execute(select(func.sum(Bill.grand_total)))
    total_revenue = revenue_res.scalar() or 0.0
    
    # 5. Recent Orders
    recent_orders_res = await db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(5)
    )
    recent_orders = recent_orders_res.scalars().all()
    
    return templates.TemplateResponse(
        request=request, name="dashboard.html", 
        context={
            "request": request,
            "stats": {
                "total": total_orders,
                "pending": pending_orders,
                "completed": completed_orders,
                "revenue": total_revenue
            },
            "recent_orders": recent_orders
        }
    )
