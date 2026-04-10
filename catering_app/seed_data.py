import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from catering_app.database import async_sessionmaker, engine
from catering_app.models import Category, FoodItem, PricingRule, UnitEnum

async def seed_data():
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # 1. Categories
        cats = [
            Category(name="Veg", description="Vegetarian Items"),
            Category(name="Non-Veg", description="Non-Vegetarian Items"),
            Category(name="Dessert", description="Sweets and Desserts"),
            Category(name="Beverage", description="Drinks and Beverages")
        ]
        session.add_all(cats)
        await session.flush() # To get ids

        cat_map = {c.name: c.id for c in cats}

        # 2. Food Items
        items = [
            FoodItem(name="Chapati", category_id=cat_map["Veg"], unit=UnitEnum.piece, base_price_per_unit=5.0),
            FoodItem(name="Steamed Rice", category_id=cat_map["Veg"], unit=UnitEnum.kg, base_price_per_unit=120.0), # Assuming kg
            FoodItem(name="Paneer Butter Masala", category_id=cat_map["Veg"], unit=UnitEnum.serving, base_price_per_unit=60.0),
            FoodItem(name="Chicken Curry", category_id=cat_map["Non-Veg"], unit=UnitEnum.piece, base_price_per_unit=80.0), # Maybe piece of chicken
            FoodItem(name="Chicken Biryani", category_id=cat_map["Non-Veg"], unit=UnitEnum.kg, base_price_per_unit=300.0),
            FoodItem(name="Dal Makhani", category_id=cat_map["Veg"], unit=UnitEnum.serving, base_price_per_unit=40.0),
            FoodItem(name="Gulab Jamun", category_id=cat_map["Dessert"], unit=UnitEnum.piece, base_price_per_unit=15.0),
            FoodItem(name="Ice Cream", category_id=cat_map["Dessert"], unit=UnitEnum.serving, base_price_per_unit=25.0),
            FoodItem(name="Lassi", category_id=cat_map["Beverage"], unit=UnitEnum.glass, base_price_per_unit=25.0),
            FoodItem(name="Mineral Water", category_id=cat_map["Beverage"], unit=UnitEnum.litre, base_price_per_unit=20.0),
        ]
        session.add_all(items)
        await session.flush()

        item_map = {i.name: i.id for i in items}

        # 3. Pricing Rules
        rules = [
            # Chapati: 1-100 pcs = ₹5 (no discount), 101-500 = ₹4.50, 500+ = ₹4.00
            PricingRule(food_item_id=item_map["Chapati"], min_quantity=1, max_quantity=100, price_per_unit=5.0),
            PricingRule(food_item_id=item_map["Chapati"], min_quantity=101, max_quantity=500, price_per_unit=4.50),
            PricingRule(food_item_id=item_map["Chapati"], min_quantity=501, max_quantity=None, price_per_unit=4.00),

            # Chicken Curry: 1-50 = ₹80, 51-200 = ₹70, 201+ = ₹65
            PricingRule(food_item_id=item_map["Chicken Curry"], min_quantity=1, max_quantity=50, price_per_unit=80.0),
            PricingRule(food_item_id=item_map["Chicken Curry"], min_quantity=51, max_quantity=200, price_per_unit=70.0),
            PricingRule(food_item_id=item_map["Chicken Curry"], min_quantity=201, max_quantity=None, price_per_unit=65.0),
            
            # Dal Makhani: 100+ servings gives 10% discount on 40 base price = 36.
            PricingRule(food_item_id=item_map["Dal Makhani"], min_quantity=100, max_quantity=None, price_per_unit=40.0, discount_percent=10.0),
        ]
        session.add_all(rules)

        await session.commit()
        print("Successfully seeded the database.")

if __name__ == "__main__":
    asyncio.run(seed_data())
