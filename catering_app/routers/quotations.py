from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, update
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime
import os

from catering_app.database import get_db
from catering_app.models import (
    Quotation, QuotationItem, QuotationItemTypeEnum, QuotationSection,
    FoodItem, Category,
)
from catering_app.templating import templates

router = APIRouter(prefix="/quotations", tags=["quotations"])


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def list_quotations(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Quotation)
        .options(selectinload(Quotation.sections).selectinload(QuotationSection.items))
        .order_by(Quotation.created_at.desc())
    )
    quotations = result.scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="quotations/list.html",
        context={"request": request, "quotations": quotations},
    )


# ── New Form ──────────────────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
async def new_quotation_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="quotations/new.html",
        context={"request": request},
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/")
async def create_quotation(
    customer_name: str = Form(...),
    customer_phone: Optional[str] = Form(None),
    function_date: str = Form(...),
    venue: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    fn_date = datetime.strptime(function_date, "%Y-%m-%d")
    q = Quotation(
        customer_name=customer_name,
        customer_phone=customer_phone,
        function_date=fn_date,
        venue=venue,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return RedirectResponse(url=f"/quotations/{q.id}", status_code=303)


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{id}", response_class=HTMLResponse)
async def quotation_detail(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Quotation)
        .options(
            selectinload(Quotation.sections).selectinload(QuotationSection.items).selectinload(QuotationItem.category),
            selectinload(Quotation.sections).selectinload(QuotationSection.items).selectinload(QuotationItem.food_item)
        )
        .where(Quotation.id == id)
    )
    quotation = result.scalar_one_or_none()
    if not quotation:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Quotation not found")

    return templates.TemplateResponse(
        request=request,
        name="quotations/detail.html",
        context={"request": request, "quotation": quotation},
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{id}", response_class=HTMLResponse)
async def delete_quotation(id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Quotation).where(Quotation.id == id))
    await db.commit()
    return HTMLResponse(
        '<div hx-get="/quotations" hx-trigger="load" hx-target="body"></div>'
    )


# ── Sections: Add/Update/Delete ───────────────────────────────────────────────

@router.post("/{id}/sections", response_class=HTMLResponse)
async def add_section(
    request: Request, 
    id: int, 
    name: str = Form(...), 
    amount: int = Form(0),
    db: AsyncSession = Depends(get_db)
):
    if not name or not name.strip():
        from fastapi.responses import Response
        return Response(headers={"HX-Refresh": "true"})

    # Get max order to place NEW section at the BOTTOM
    max_order_res = await db.execute(select(func.max(QuotationSection.display_order)).where(QuotationSection.quotation_id == id))
    max_order = max_order_res.scalar() or 0
    
    new_section = QuotationSection(
        quotation_id=id,
        name=name.strip().upper(),
        amount=amount,
        display_order=max_order + 1
    )
    db.add(new_section)
    await db.commit()
    
    from fastapi.responses import Response
    return Response(headers={"HX-Refresh": "true"})

@router.delete("/{id}/sections/{section_id}", response_class=HTMLResponse)
async def delete_section(id: int, section_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(QuotationSection).where(QuotationSection.id == section_id, QuotationSection.quotation_id == id))
    await db.commit()
    from fastapi.responses import Response
    return Response(headers={"HX-Refresh": "true"})

@router.post("/{id}/sections/{section_id}/update", response_class=HTMLResponse)
async def update_section(
    request: Request, 
    id: int, 
    section_id: int, 
    name: Optional[str] = Form(None), 
    amount: Optional[int] = Form(None), 
    db: AsyncSession = Depends(get_db)
):
    stmt = update(QuotationSection).where(QuotationSection.id == section_id, QuotationSection.quotation_id == id)
    if name is not None:
        stmt = stmt.values(name=name)
    if amount is not None:
        stmt = stmt.values(amount=amount)
    
    await db.execute(stmt)
    await db.commit()
    
    # Trigger refresh of the grand total on the page
    response = HTMLResponse("")
    response.headers["HX-Trigger"] = "quotationChanged"
    return response

@router.get("/{id}/total", response_class=HTMLResponse)
async def get_quotation_total(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Quotation)
        .options(selectinload(Quotation.sections).selectinload(QuotationSection.items))
        .where(Quotation.id == id)
    )
    q = result.scalar_one()
    
    return HTMLResponse(f'{q.total_amount:,}')


# ── HTMX: Search (categories + items) ────────────────────────────────────────

@router.get("/{id}/search", response_class=HTMLResponse)
async def search_items(
    request: Request,
    id: int,
    section_id: int,
    q: str = "",
    db: AsyncSession = Depends(get_db),
):
    if not q or len(q) < 1:
        return HTMLResponse(f"""
        <div class="flex flex-col items-center justify-center py-8 text-gray-300">
            <svg class="w-8 h-8 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            <span class="text-xs font-bold uppercase tracking-widest">Type to search</span>
        </div>
        """)

    # Search categories
    cat_result = await db.execute(
        select(Category).where(Category.name.ilike(f"%{q}%")).order_by(Category.name).limit(10)
    )
    categories = cat_result.scalars().all()

    # Search individual food items
    item_result = await db.execute(
        select(FoodItem)
        .options(selectinload(FoodItem.category))
        .where(FoodItem.name.ilike(f"%{q}%"), FoodItem.is_active == True)
        .order_by(FoodItem.name)
        .limit(20)
    )
    food_items = item_result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="quotations/_search_results.html",
        context={
            "request": request,
            "quotation_id": id,
            "section_id": section_id,
            "categories": categories,
            "food_items": food_items,
        },
    )

@router.get("/{id}/category/{cat_id}/items", response_class=HTMLResponse)
async def get_category_items(
    request: Request,
    id: int,
    section_id: int,
    cat_id: int,
    db: AsyncSession = Depends(get_db)
):
    items_res = await db.execute(
        select(FoodItem).where(FoodItem.category_id == cat_id, FoodItem.is_active == True).order_by(FoodItem.name)
    )
    items = items_res.scalars().all()
    
    cat_res = await db.execute(select(Category).where(Category.id == cat_id))
    category = cat_res.scalar_one()

    return templates.TemplateResponse(
        request=request,
        name="quotations/_category_items_drilldown.html",
        context={
            "request": request,
            "quotation_id": id,
            "section_id": section_id,
            "category": category,
            "items": items
        }
    )


# ── HTMX: Add Items ───────────────────────────────────────────────────────────

@router.post("/{id}/sections/{section_id}/items/standalone", response_class=HTMLResponse)
async def add_item(
    request: Request,
    id: int,
    section_id: int,
    food_item_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    # Get current max order in section
    max_order_res = await db.execute(select(func.max(QuotationItem.display_order)).where(QuotationItem.section_id == section_id))
    max_order = max_order_res.scalar() or 0
    
    food_res = await db.execute(select(FoodItem).where(FoodItem.id == food_item_id))
    fi = food_res.scalar_one_or_none()
    if not fi:
        return ""

    qi = QuotationItem(
        section_id=section_id,
        food_item_id=fi.id,
        label=fi.name,
        item_type=QuotationItemTypeEnum.standalone_item,
        display_order=max_order + 1,
    )
    db.add(qi)
    await db.commit()
    
    return await _render_section_items(request, section_id, db)

@router.post("/{id}/sections/{section_id}/items/category-header", response_class=HTMLResponse)
async def add_category_header(
    request: Request,
    id: int,
    section_id: int,
    category_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    max_order_res = await db.execute(select(func.max(QuotationItem.display_order)).where(QuotationItem.section_id == section_id))
    max_order = max_order_res.scalar() or 0
    
    cat_res = await db.execute(select(Category).where(Category.id == category_id))
    cat = cat_res.scalar_one_or_none()
    if not cat: return ""

    qi = QuotationItem(
        section_id=section_id,
        category_id=cat.id,
        label=cat.name,
        item_type=QuotationItemTypeEnum.category_item,
        display_order=max_order + 1,
    )
    db.add(qi)
    await db.commit()
    return await _render_section_items(request, section_id, db)

@router.post("/{id}/sections/{section_id}/items/bulk", response_class=HTMLResponse)
async def add_bulk_items(
    request: Request,
    id: int,
    section_id: int,
    item_ids: list[int] = Form(...),
    category_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    max_order_res = await db.execute(select(func.max(QuotationItem.display_order)).where(QuotationItem.section_id == section_id))
    max_order = max_order_res.scalar() or 0
    
    # If category_id is provided, add the header first
    if category_id:
        cat_res = await db.execute(select(Category).where(Category.id == category_id))
        cat = cat_res.scalar_one_or_none()
        if cat:
            header = QuotationItem(
                section_id=section_id,
                category_id=cat.id,
                label=cat.name,
                item_type=QuotationItemTypeEnum.category_item,
                display_order=max_order + 1
            )
            db.add(header)
            max_order += 1

    # Add items
    food_items_res = await db.execute(select(FoodItem).where(FoodItem.id.in_(item_ids)))
    food_items = food_items_res.scalars().all()
    
    # Keep selection order if possible, though in_() might shuffle. 
    # For now, just add them
    for idx, fi in enumerate(food_items):
        qi = QuotationItem(
            section_id=section_id,
            food_item_id=fi.id,
            category_id=fi.category_id,
            label=fi.name,
            item_type=QuotationItemTypeEnum.category_item if category_id else QuotationItemTypeEnum.standalone_item,
            display_order=max_order + 1 + idx,
        )
        db.add(qi)
        
    await db.commit()
    return await _render_section_items(request, section_id, db)


@router.post("/{id}/sections/{section_id}/items/{item_id}/update", response_class=HTMLResponse)
async def update_item_amount(
    request: Request,
    id: int,
    section_id: int,
    item_id: int,
    amount: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        update(QuotationItem)
        .where(QuotationItem.id == item_id, QuotationItem.section_id == section_id)
        .values(amount=amount)
    )
    await db.commit()

    return await _render_section_items(request, section_id, db)


# ── HTMX: Remove Item ─────────────────────────────────────────────────────────

@router.delete("/{id}/sections/{section_id}/items/{item_id}", response_class=HTMLResponse)
async def remove_quotation_item(
    request: Request,
    id: int,
    section_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    # Fetch the item first to see if it's a category header
    item_res = await db.execute(select(QuotationItem).where(QuotationItem.id == item_id))
    item = item_res.scalar_one_or_none()
    
    if item:
        # If it's a category header (category_id set, but no food_item_id)
        if item.item_type == QuotationItemTypeEnum.category_item and item.food_item_id is None and item.category_id is not None:
            # Delete the header AND all items under this category in this section
            await db.execute(
                delete(QuotationItem)
                .where(
                    QuotationItem.section_id == section_id,
                    QuotationItem.category_id == item.category_id
                )
            )
        else:
            # Delete just this one item
            await db.execute(delete(QuotationItem).where(QuotationItem.id == item_id))
            
        await db.commit()
        
    return await _render_section_items(request, section_id, db)


# ── PDF Download ──────────────────────────────────────────────────────────────

@router.get("/{id}/pdf")
async def download_quotation_pdf(id: int, db: AsyncSession = Depends(get_db)):
    from catering_app.services.quotation_pdf import generate_quotation_pdf
    pdf_path = await generate_quotation_pdf(db, id)
    abs_path = os.path.join(os.getcwd(), "catering_app", pdf_path.lstrip("/"))
    return FileResponse(abs_path, filename=f"Quotation_{id}.pdf", media_type="application/pdf")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _render_section_items(request: Request, section_id: int, db: AsyncSession) -> HTMLResponse:
    res = await db.execute(
        select(QuotationItem)
        .options(selectinload(QuotationItem.category), selectinload(QuotationItem.food_item))
        .where(QuotationItem.section_id == section_id)
        .order_by(QuotationItem.display_order)
    )
    items = res.scalars().all()
    
    # We need the quotation_id for the links in partial
    sec_res = await db.execute(select(QuotationSection).where(QuotationSection.id == section_id))
    section = sec_res.scalar_one()
    
    response = templates.TemplateResponse(
        request=request,
        name="quotations/_section_items.html",
        context={"request": request, "items": items, "section": section, "quotation_id": section.quotation_id},
    )
    response.headers["HX-Trigger"] = "quotationChanged"
    return response
