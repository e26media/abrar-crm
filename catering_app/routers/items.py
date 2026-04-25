from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional

from catering_app.database import get_db
from catering_app.models import FoodItem, Category
from catering_app.templating import templates

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/", response_class=HTMLResponse)
async def list_items(request: Request, category: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    # Use selectinload for the category relationship
    query = select(FoodItem).options(selectinload(FoodItem.category)).where(FoodItem.is_active == True)
    
    if category and category.strip():
        query = query.join(Category).where(Category.name.ilike(f"%{category}%"))
    
    query = query.order_by(FoodItem.name)
    result = await db.execute(query)
    items = result.scalars().all()
    
    # Debug info for logs
    print(f"DEBUG: Found {len(items)} active items. Filter: '{category}'")
    
    categories_result = await db.execute(select(Category).order_by(Category.name))
    categories = categories_result.scalars().all()
    print(f"DEBUG: Found {len(categories)} categories.")
        
    template_name = "items/list.html"
    if request.headers.get("HX-Request"):
        template_name = "items/_items_list_partial.html"
        
    return templates.TemplateResponse(
        request=request, name=template_name, 
        context={
            "request": request, 
            "items_data": items, 
            "categories": categories, 
            "active_category": category
        }
    )

@router.get("/new", response_class=HTMLResponse)
async def new_item_form(request: Request, db: AsyncSession = Depends(get_db)):
    categories_result = await db.execute(select(Category))
    categories = categories_result.scalars().all()
    return templates.TemplateResponse(request=request, name="items/new.html", context={"request": request, "categories": categories})

@router.post("/")
async def create_item(
    name: str = Form(...),
    category_id: int = Form(...),
    unit: str = Form("serving"),
    base_price_per_unit: float = Form(0.0),
    db: AsyncSession = Depends(get_db)
):
    new_item = FoodItem(
        name=name,
        category_id=category_id,
        unit=unit,
        base_price_per_unit=base_price_per_unit
    )
    db.add(new_item)
    await db.commit()
    # Redirecting normally (HTMX might intercept depending on how form is setup, but let's assume standard redirect)
    return RedirectResponse(url="/items", status_code=303)

@router.get("/{id}/edit", response_class=HTMLResponse)
async def edit_item_form(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FoodItem).where(FoodItem.id == id))
    item = result.scalar_one_or_none()
    categories_result = await db.execute(select(Category))
    categories = categories_result.scalars().all()
    return templates.TemplateResponse(request=request, name="items/_edit_form.html", context={"request": request, "item": item, "categories": categories})

@router.put("/{id}", response_class=HTMLResponse)
async def update_item(
    request: Request,
    id: int,
    name: str = Form(...),
    category_id: int = Form(...),
    unit: str = Form("serving"),
    base_price_per_unit: float = Form(0.0),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(FoodItem).where(FoodItem.id == id))
    item = result.scalar_one_or_none()
    if item:
        item.name = name
        item.category_id = category_id
        item.unit = unit
        item.base_price_per_unit = base_price_per_unit
        await db.commit()
        await db.refresh(item)
    
    # Return the updated row
    # Need category name for the row
    cat_result = await db.execute(select(Category).where(Category.id == item.category_id))
    cat = cat_result.scalar_one_or_none()
    return templates.TemplateResponse(request=request, name="items/_item_row.html", context={"request": request, "item": item, "category": cat})

@router.delete("/{id}", response_class=HTMLResponse)
async def delete_item(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FoodItem).where(FoodItem.id == id))
    item = result.scalar_one_or_none()
    if item:
        item.is_active = False
        await db.commit()
    return HTMLResponse("") # Empty response removes the row in HTMX if target is outerHTML

# htmx-partial
@router.get("/search", response_class=HTMLResponse)
async def search_items(request: Request, q: str = "", limit: int = 10, db: AsyncSession = Depends(get_db)):
    if not q:
        return HTMLResponse("")
    
    query = select(FoodItem).options(selectinload(FoodItem.category))\
                .where(FoodItem.is_active == True, FoodItem.name.ilike(f"%{q}%")).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return templates.TemplateResponse(request=request, name="items/_search_results.html", context={"request": request, "items_data": items})
