from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from catering_app.models import FoodItem, PricingRule, OrderItem
from catering_app.schemas import PriceCalculationResult, OrderTotalResult
from catering_app.config import settings

async def calculate_item_price(
    session: AsyncSession, 
    food_item_id: int, 
    quantity_per_plate: float, 
    num_plates: int
) -> PriceCalculationResult:
    total_quantity = quantity_per_plate * num_plates
    
    # Get the food item base price
    result = await session.execute(select(FoodItem).where(FoodItem.id == food_item_id))
    food_item = result.scalar_one_or_none()
    
    if not food_item:
        raise ValueError(f"Food item {food_item_id} not found")

    # Look for matching pricing rule
    # min_quantity <= total_quantity AND (max_quantity is NULL OR total_quantity <= max_quantity)
    rule_result = await session.execute(
        select(PricingRule).where(
            and_(
                PricingRule.food_item_id == food_item_id,
                PricingRule.min_quantity <= total_quantity,
                or_(
                    PricingRule.max_quantity.is_(None),
                    PricingRule.max_quantity >= total_quantity
                )
            )
        ).order_by(PricingRule.min_quantity.desc()).limit(1)
    )
    matching_rule = rule_result.scalar_one_or_none()

    if matching_rule:
        discount = matching_rule.price_per_unit * (matching_rule.discount_percent / 100.0)
        unit_price = matching_rule.price_per_unit - discount
        discount_applied = discount * total_quantity
    else:
        # Fallback to base price
        unit_price = food_item.base_price_per_unit
        discount_applied = 0.0

    line_total = unit_price * total_quantity

    return PriceCalculationResult(
        unit_price=unit_price,
        discount_applied=discount_applied,
        line_total=line_total
    )

async def calculate_order_total(session: AsyncSession, order_id: int, num_plates: int) -> OrderTotalResult:
    # Fetch all order items
    result = await session.execute(
        select(OrderItem, FoodItem)
        .join(FoodItem, OrderItem.food_item_id == FoodItem.id)
        .where(OrderItem.order_id == order_id)
    )
    items_data = result.all()

    line_items_detailed = []
    subtotal = 0.0

    for order_item, food_item in items_data:
        calc_result = await calculate_item_price(
            session, 
            food_item_id=food_item.id,
            quantity_per_plate=order_item.quantity_per_plate,
            num_plates=num_plates
        )
        
        # We can update the OrderItem's calculated_total here or leave it to the caller
        order_item.unit_price = calc_result.unit_price
        order_item.calculated_total = calc_result.line_total
        
        line_items_detailed.append({
            "order_item_id": order_item.id,
            "food_item_id": food_item.id,
            "food_item_name": food_item.name,
            "quantity_per_plate": order_item.quantity_per_plate,
            "total_quantity": order_item.quantity_per_plate * num_plates,
            "unit_price": calc_result.unit_price,
            "line_total": calc_result.line_total
        })
        
        subtotal += calc_result.line_total

    tax_amount = subtotal * (settings.tax_percent / 100.0)
    grand_total = subtotal + tax_amount
    price_per_plate = grand_total / num_plates if num_plates > 0 else 0.0

    return OrderTotalResult(
        line_items=line_items_detailed,
        subtotal=subtotal,
        tax_amount=tax_amount,
        grand_total=grand_total,
        price_per_plate=price_per_plate
    )
