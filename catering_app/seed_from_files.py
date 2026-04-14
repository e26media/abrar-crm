import asyncio
import os
import traceback
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from catering_app.database import AsyncSessionLocal, engine
from catering_app.models import Category, FoodItem, UnitEnum

async def seed_from_files():
    try:
        # Paths to the files
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        categories_file = os.path.join(base_dir, "menus", "categories.txt")
        menus_file = os.path.join(base_dir, "menus", "all_menu_list.txt")

        if not os.path.exists(categories_file) or not os.path.exists(menus_file):
            print("Error: Menu files not found.")
            return

        # 1. Read and clean categories from categories.txt
        with open(categories_file, 'r', encoding='utf-8') as f:
            category_names = sorted(list(set([line.strip() for line in f if line.strip()])))
        
        print(f"Found {len(category_names)} unique categories in categories.txt")

        # 2. Parse menu list and discover extra categories
        menu_data = {}
        current_category = None
        extra_categories = set()
        
        with open(menus_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('●'):
                    raw_cat = line.lstrip('●').strip().rstrip(':').strip()
                    # Fuzzy match with existing category names
                    matched_cat = next((c for c in category_names if c.lower() == raw_cat.lower()), None)
                    if matched_cat:
                        current_category = matched_cat
                    else:
                        current_category = raw_cat
                        extra_categories.add(raw_cat)
                        
                    if current_category not in menu_data:
                        menu_data[current_category] = []
                elif current_category:
                    item_name = line.lstrip('•').strip()
                    if item_name:
                        menu_data[current_category].append(item_name)

        all_needed_categories = set(category_names) | extra_categories
        print(f"Total categories to process (including extras from menu list): {len(all_needed_categories)}")

        async with AsyncSessionLocal() as session:
            # 3. Deactivate all existing items first
            print("Deactivating all existing menu items...")
            await session.execute(update(FoodItem).values(is_active=False))
            await session.flush()

            # 4. Handle Categories
            existing_cats_result = await session.execute(select(Category))
            existing_cats_map = {c.name.lower(): c for c in existing_cats_result.scalars().all()}
            
            cat_obj_map = {} # lower_name -> Category object
            
            for cat_name in all_needed_categories:
                low_name = cat_name.lower()
                if low_name in existing_cats_map:
                    cat_obj_map[low_name] = existing_cats_map[low_name]
                else:
                    new_cat = Category(name=cat_name)
                    session.add(new_cat)
                    cat_obj_map[low_name] = new_cat
            
            await session.flush() # Ensure all categories have IDs

            # 5. Insert/Activate Food Items
            total_created = 0
            total_activated = 0
            
            for cat_name, item_list in menu_data.items():
                cat_obj = cat_obj_map[cat_name.lower()]
                for item_name in item_list:
                    # Check if item exists in this category
                    existing_item_result = await session.execute(
                        select(FoodItem).where(FoodItem.name == item_name, FoodItem.category_id == cat_obj.id)
                    )
                    existing_item = existing_item_result.scalar_one_or_none()
                    
                    if existing_item:
                        existing_item.is_active = True
                        total_activated += 1
                    else:
                        new_item = FoodItem(
                            name=item_name,
                            category_id=cat_obj.id,
                            unit=UnitEnum.serving,
                            base_price_per_unit=0.0,
                            is_active=True
                        )
                        session.add(new_item)
                        total_created += 1
            
            await session.commit()
            print(f"Success! Created {total_created} new items, activated {total_activated} existing items.")
            print("Old menus (not in the text files) are now hidden.")

    except Exception:
        print("An error occurred during seeding:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(seed_from_files())
