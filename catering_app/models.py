import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from catering_app.database import Base

class UnitEnum(str, enum.Enum):
    piece = "piece"
    kg = "kg"
    litre = "litre"
    serving = "serving"
    glass = "glass"
    plate = "plate"
    sqft = "sqft"

class OrderStatusEnum(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    billed = "billed"

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(255), nullable=True)

    food_items = relationship("FoodItem", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"

class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    unit = Column(Enum(UnitEnum), nullable=True, default=UnitEnum.serving)
    base_price_per_unit = Column(Float, nullable=True, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("Category", back_populates="food_items")
    pricing_rules = relationship("PricingRule", back_populates="food_item", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="food_item")

    def __repr__(self):
        return f"<FoodItem {self.name} ({self.unit})>"

class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id = Column(Integer, primary_key=True, index=True)
    food_item_id = Column(Integer, ForeignKey("food_items.id"), nullable=False)
    min_quantity = Column(Integer, nullable=False)
    max_quantity = Column(Integer, nullable=True) # Null means infinity
    price_per_unit = Column(Float, nullable=False)
    discount_percent = Column(Float, default=0.0)

    food_item = relationship("FoodItem", back_populates="pricing_rules")

    def __repr__(self):
        return f"<PricingRule for item_id={self.food_item_id}: {self.min_quantity}-{self.max_quantity} = {self.price_per_unit}>"

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(100), nullable=False)
    event_date = Column(DateTime, nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(100), nullable=True)
    venue = Column(String(255), nullable=True)
    num_plates = Column(Integer, nullable=False, default=1)
    status = Column(Enum(OrderStatusEnum), default=OrderStatusEnum.draft)
    manual_total = Column(Float, nullable=True)
    manual_price_per_plate = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    bill = relationship("Bill", back_populates="order", uselist=False)

    def __repr__(self):
        return f"<Order {self.id} - {self.customer_name}>"

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    food_item_id = Column(Integer, ForeignKey("food_items.id"), nullable=False)
    quantity_per_plate = Column(Float, nullable=False, default=1.0)
    unit_price = Column(Float, nullable=False)
    calculated_total = Column(Float, nullable=False, default=0.0)

    order = relationship("Order", back_populates="items")
    food_item = relationship("FoodItem", back_populates="order_items")

    def __repr__(self):
        return f"<OrderItem order={self.order_id} item={self.food_item_id}>"

class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True, nullable=True)
    customer_name = Column(String(100), nullable=True)
    subtotal = Column(Float, nullable=True)
    tax_percent = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)
    grand_total = Column(Float, nullable=False, default=0.0)
    advance_payment = Column(Float, nullable=False, default=0.0)
    balance_amount = Column(Float, nullable=False, default=0.0)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    pdf_path = Column(String(255), nullable=True)

    order = relationship("Order", back_populates="bill")
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan", order_by="BillItem.display_order")

    def __repr__(self):
        return f"<Bill {self.id} for Order {self.order_id}>"

class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    item_date = Column(DateTime, nullable=True)
    event_name = Column(String(100), nullable=True)
    venue = Column(String(255), nullable=True)
    particulars = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    discount_amount = Column(Float, nullable=True, default=0.0)
    display_order = Column(Integer, nullable=False, default=0)

    bill = relationship("Bill", back_populates="items")

    def __repr__(self):
        return f"<BillItem {self.particulars} for Bill {self.bill_id}>"


# ── Quotation Models ──────────────────────────────────────────────────────────

class QuotationItemTypeEnum(str, enum.Enum):
    category_item  = "category_item"   # item added under a category group
    standalone_item = "standalone_item" # item added individually (bullet style)


class Quotation(Base):
    __tablename__ = "quotations"

    id            = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(100), nullable=True)
    function_date = Column(DateTime, nullable=False)
    venue         = Column(String(255), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    sections = relationship(
        "QuotationSection",
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationSection.display_order",
    )

    def __repr__(self):
        return f"<Quotation {self.id} - {self.customer_name}>"

    @property
    def total_amount(self):
        """Calculates total amount from sections and individual items."""
        total = 0
        for s in self.sections:
            amt = s.amount or 0
            total += amt
            if amt == 0:
                # If section has no base amount, add up standalone items
                total += sum((i.amount or 0) for i in s.items 
                             if i.amount and i.item_type == QuotationItemTypeEnum.standalone_item)
        return total


class QuotationSection(Base):
    __tablename__ = "quotation_sections"

    id             = Column(Integer, primary_key=True, index=True)
    quotation_id   = Column(Integer, ForeignKey("quotations.id"), nullable=False)
    name           = Column(String(100), nullable=True)   # e.g. "IFTHAR MENU"
    amount         = Column(Integer, nullable=False, default=0)
    display_order  = Column(Integer, nullable=False, default=0)

    quotation = relationship("Quotation", back_populates="sections")
    items     = relationship(
        "QuotationItem",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="QuotationItem.display_order",
    )

    def __repr__(self):
        return f"<QuotationSection {self.name} of Quotation {self.quotation_id}>"


class QuotationItem(Base):
    __tablename__ = "quotation_items"

    id             = Column(Integer, primary_key=True, index=True)
    section_id     = Column(Integer, ForeignKey("quotation_sections.id"), nullable=False)
    food_item_id   = Column(Integer, ForeignKey("food_items.id"), nullable=True)
    category_id    = Column(Integer, ForeignKey("categories.id"), nullable=True)
    label          = Column(String(150), nullable=False)   # display name
    item_type      = Column(Enum(QuotationItemTypeEnum), nullable=False)
    amount         = Column(Integer, nullable=True)        # individual item price
    display_order  = Column(Integer, nullable=False, default=0)

    section    = relationship("QuotationSection", back_populates="items")
    food_item  = relationship("FoodItem")
    category   = relationship("Category")

    def __repr__(self):
        return f"<QuotationItem {self.label}>"
