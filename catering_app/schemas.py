from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime
from catering_app.models import UnitEnum, OrderStatusEnum

# Category Schemas
class CategoryBase(BaseModel):
    name: str = Field(..., max_length=50)
    description: Optional[str] = Field(None, max_length=255)

class CategoryCreate(CategoryBase):
    pass

class CategoryRead(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

# PricingRule Schemas
class PricingRuleBase(BaseModel):
    min_quantity: int
    max_quantity: Optional[int] = None
    price_per_unit: float
    discount_percent: float = 0.0

class PricingRuleCreate(PricingRuleBase):
    food_item_id: int

class PricingRuleRead(PricingRuleBase):
    id: int
    food_item_id: int

    model_config = ConfigDict(from_attributes=True)

# FoodItem Schemas
class FoodItemBase(BaseModel):
    name: str = Field(..., max_length=100)
    category_id: int
    unit: UnitEnum
    base_price_per_unit: float
    is_active: bool = True

class FoodItemCreate(FoodItemBase):
    pass

class FoodItemUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    unit: Optional[UnitEnum] = None
    base_price_per_unit: Optional[float] = None
    is_active: Optional[bool] = None

class FoodItemRead(FoodItemBase):
    id: int
    created_at: datetime
    category: Optional[CategoryRead] = None
    pricing_rules: List[PricingRuleRead] = []

    model_config = ConfigDict(from_attributes=True)

# OrderItem Schemas
class OrderItemBase(BaseModel):
    food_item_id: int
    quantity_per_plate: float = 1.0

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemRead(OrderItemBase):
    id: int
    order_id: int
    unit_price: float
    calculated_total: float
    food_item: Optional[FoodItemRead] = None

    model_config = ConfigDict(from_attributes=True)

# Order Schemas
class OrderBase(BaseModel):
    event_name: str = Field(..., max_length=100)
    event_date: datetime
    customer_name: str = Field(..., max_length=100)
    customer_phone: str = Field(..., max_length=20)
    venue: Optional[str] = Field(None, max_length=255)
    num_plates: int = Field(default=1, gt=0)

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    event_name: Optional[str] = None
    event_date: Optional[datetime] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    venue: Optional[str] = None
    num_plates: Optional[int] = Field(None, gt=0)
    status: Optional[OrderStatusEnum] = None

class OrderRead(OrderBase):
    id: int
    status: OrderStatusEnum
    created_at: datetime
    items: List[OrderItemRead] = []

    model_config = ConfigDict(from_attributes=True)


# Bill Schemas
class BillItemBase(BaseModel):
    item_date: Optional[datetime] = None
    event_name: Optional[str] = None
    venue: Optional[str] = None
    particulars: str
    amount: float
    discount_amount: float = 0.0
    display_order: int = 0

class BillItemCreate(BillItemBase):
    pass

class BillItemRead(BillItemBase):
    id: int
    bill_id: int

    model_config = ConfigDict(from_attributes=True)

class BillBase(BaseModel):
    customer_name: Optional[str] = None
    grand_total: float = 0.0
    advance_payment: float = 0.0
    balance_amount: float = 0.0
    pdf_path: Optional[str] = None

class BillCreate(BillBase):
    order_id: Optional[int] = None
    items: List[BillItemCreate] = []

class BillRead(BillBase):
    id: int
    order_id: Optional[int]
    generated_at: datetime
    items: List[BillItemRead] = []

    model_config = ConfigDict(from_attributes=True)

# Calculation Result Schemas
class PriceCalculationResult(BaseModel):
    unit_price: float
    discount_applied: float
    line_total: float

class OrderTotalResult(BaseModel):
    line_items: List[dict] # Detailed line item info
    subtotal: float
    tax_amount: float
    grand_total: float
    price_per_plate: float
