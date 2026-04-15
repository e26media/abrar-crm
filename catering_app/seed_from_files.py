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
        
        # Multiple menu files
        menu_files = [
            os.path.join(base_dir, "menus", "all_menu_list.txt"),
            os.path.join(base_dir, "menus", "rentals.txt")
        ]

        if not os.path.exists(categories_file):
            print("Error: categories.txt not found.")
            return

        # 1. Read and clean categories from categories.txt
        with open(categories_file, 'r', encoding='utf-8') as f:
            category_names = sorted(list(set([line.strip() for line in f if line.strip()])))
        
        print(f"Found {len(category_names)} unique categories in categories.txt")

        # 2. Parse menu list and discover extra categories
        menu_data = {} # Category Name -> List of (item_name, price, unit)
        extra_categories = set()
        
        for menus_file in menu_files:
            if not os.path.exists(menus_file):
                print(f"Skipping {menus_file}: file not found.")
                continue
            
            print(f"Processing {os.path.basename(menus_file)}...")
            current_category = None
            
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
                        # Parsing logic: Item Name | Price | Unit
                        parts = [p.strip() for p in line.lstrip('•').split('|')]
                        item_name = parts[0]
                        price = float(parts[1]) if len(parts) > 1 and parts[1] else 0.0
                        unit_str = parts[2].lower() if len(parts) > 2 and parts[2] else 'serving'
                        
                        # Validate unit
                        try:
                            unit = UnitEnum(unit_str)
                        except ValueError:
                            unit = UnitEnum.serving
                            
                        if item_name:
                            menu_data[current_category].append((item_name, price, unit))

        all_needed_categories = set(category_names) | extra_categories
        print(f"Total categories to process: {len(all_needed_categories)}")

        async with AsyncSessionLocal() as session:
            # Note: Global deactivation removed as requested to "keep existing item active"
            
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
            total_updated = 0
            
            for cat_name, item_list in menu_data.items():
                cat_obj = cat_obj_map[cat_name.lower()]
                for item_name, price, unit in item_list:
                    # Check if item exists in this category
                    existing_item_result = await session.execute(
                        select(FoodItem).where(FoodItem.name == item_name, FoodItem.category_id == cat_obj.id)
                    )
                    existing_item = existing_item_result.scalar_one_or_none()
                    
                    if existing_item:
                        existing_item.is_active = True
                        existing_item.base_price_per_unit = price
                        existing_item.unit = unit
                        total_updated += 1
                    else:
                        new_item = FoodItem(
                            name=item_name,
                            category_id=cat_obj.id,
                            unit=unit,
                            base_price_per_unit=price,
                            is_active=True
                        )
                        session.add(new_item)
                        total_created += 1
            
            await session.commit()
            print(f"Success! Created {total_created} new items, updated {total_updated} existing items.")
            print("Old menus (not in the text files) are now hidden.")

    except Exception:
        print("An error occurred during seeding:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(seed_from_files())
