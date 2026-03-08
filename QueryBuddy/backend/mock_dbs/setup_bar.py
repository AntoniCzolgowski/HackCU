"""Create and seed a bar/restaurant MongoDB database."""
import pymongo


def setup_bar():
    """
    Connect to the local MongoDB instance and populate a 'bar' database
    with collections for drinks, food, employees, tabs, inventory, etc.
    Returns the pymongo client or None if MongoDB is unavailable.
    """
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=3000)
        client.server_info()  # fail fast if MongoDB is not running
    except Exception as e:
        print(f"Bar MongoDB setup skipped — cannot connect: {e}")
        return None

    db = client["bar"]

    # Only seed if the database is empty (idempotent)
    if "employees" in db.list_collection_names():
        print("Bar MongoDB already seeded, skipping.")
        return client

    # ── Employees ─────────────────────────────────────────────────────────────
    db.employees.insert_many([
        {"employee_id": 1,  "name": "Jake Rivera",      "role": "Bartender",  "hourly_wage": 22.00, "hire_date": "2023-03-15", "is_active": True},
        {"employee_id": 2,  "name": "Mia Chen",         "role": "Bartender",  "hourly_wage": 22.00, "hire_date": "2023-06-01", "is_active": True},
        {"employee_id": 3,  "name": "Carlos Gutierrez",  "role": "Head Chef",  "hourly_wage": 28.00, "hire_date": "2022-11-10", "is_active": True},
        {"employee_id": 4,  "name": "Priya Patel",      "role": "Line Cook",  "hourly_wage": 18.50, "hire_date": "2023-09-20", "is_active": True},
        {"employee_id": 5,  "name": "Sam Okafor",       "role": "Server",     "hourly_wage": 15.00, "hire_date": "2024-01-08", "is_active": True},
        {"employee_id": 6,  "name": "Lily Tran",        "role": "Server",     "hourly_wage": 15.00, "hire_date": "2023-07-22", "is_active": True},
        {"employee_id": 7,  "name": "Devon Brooks",     "role": "Host",       "hourly_wage": 14.00, "hire_date": "2024-02-14", "is_active": True},
        {"employee_id": 8,  "name": "Ava Martinez",     "role": "Barback",    "hourly_wage": 16.00, "hire_date": "2023-12-01", "is_active": True},
        {"employee_id": 9,  "name": "Noah Kim",         "role": "Manager",    "hourly_wage": 30.00, "hire_date": "2022-06-15", "is_active": True},
        {"employee_id": 10, "name": "Zoe Williams",     "role": "Dishwasher", "hourly_wage": 14.50, "hire_date": "2024-03-01", "is_active": False},
    ])

    # ── Drinks ────────────────────────────────────────────────────────────────
    db.drinks.insert_many([
        # Cocktails
        {"drink_id": 1,  "name": "Old Fashioned",       "category": "Cocktails",     "price": 14.00, "abv": 32.0, "is_available": True},
        {"drink_id": 2,  "name": "Margarita",           "category": "Cocktails",     "price": 13.00, "abv": 20.0, "is_available": True},
        {"drink_id": 3,  "name": "Espresso Martini",    "category": "Cocktails",     "price": 15.00, "abv": 22.0, "is_available": True},
        {"drink_id": 4,  "name": "Mojito",              "category": "Cocktails",     "price": 12.00, "abv": 15.0, "is_available": True},
        {"drink_id": 5,  "name": "Negroni",             "category": "Cocktails",     "price": 14.00, "abv": 28.0, "is_available": True},
        {"drink_id": 6,  "name": "Manhattan",           "category": "Cocktails",     "price": 15.00, "abv": 30.0, "is_available": True},
        # Beer
        {"drink_id": 7,  "name": "IPA Draft",           "category": "Beer",          "price":  8.00, "abv":  6.5, "is_available": True},
        {"drink_id": 8,  "name": "Pilsner Draft",       "category": "Beer",          "price":  7.00, "abv":  4.8, "is_available": True},
        {"drink_id": 9,  "name": "Stout Draft",         "category": "Beer",          "price":  8.50, "abv":  5.5, "is_available": True},
        {"drink_id": 10, "name": "Lager Bottle",        "category": "Beer",          "price":  6.00, "abv":  4.2, "is_available": True},
        # Wine
        {"drink_id": 11, "name": "House Red (glass)",   "category": "Wine",          "price": 11.00, "abv": 13.5, "is_available": True},
        {"drink_id": 12, "name": "House White (glass)", "category": "Wine",          "price": 11.00, "abv": 12.0, "is_available": True},
        {"drink_id": 13, "name": "Prosecco (glass)",    "category": "Wine",          "price": 12.00, "abv": 11.0, "is_available": True},
        # Spirits
        {"drink_id": 14, "name": "Whiskey Neat",        "category": "Spirits",       "price": 12.00, "abv": 40.0, "is_available": True},
        {"drink_id": 15, "name": "Tequila Shot",        "category": "Shots",         "price":  8.00, "abv": 40.0, "is_available": True},
        {"drink_id": 16, "name": "Vodka Soda",          "category": "Spirits",       "price": 10.00, "abv": 12.0, "is_available": True},
        # Non-Alcoholic
        {"drink_id": 17, "name": "Virgin Mojito",       "category": "Non-Alcoholic", "price":  7.00, "abv":  0.0, "is_available": True},
        {"drink_id": 18, "name": "Craft Soda",          "category": "Non-Alcoholic", "price":  5.00, "abv":  0.0, "is_available": True},
        {"drink_id": 19, "name": "Espresso",            "category": "Non-Alcoholic", "price":  4.00, "abv":  0.0, "is_available": True},
    ])

    # ── Food ──────────────────────────────────────────────────────────────────
    db.food.insert_many([
        # Appetizers
        {"food_id": 1,  "name": "Loaded Nachos",        "category": "Appetizers", "price": 12.00, "is_vegetarian": True,  "is_available": True},
        {"food_id": 2,  "name": "Wings (12 pc)",        "category": "Appetizers", "price": 15.00, "is_vegetarian": False, "is_available": True},
        {"food_id": 3,  "name": "Mozzarella Sticks",    "category": "Appetizers", "price": 10.00, "is_vegetarian": True,  "is_available": True},
        {"food_id": 4,  "name": "Bruschetta",           "category": "Appetizers", "price":  9.00, "is_vegetarian": True,  "is_available": True},
        {"food_id": 5,  "name": "Calamari",             "category": "Appetizers", "price": 13.00, "is_vegetarian": False, "is_available": True},
        # Mains
        {"food_id": 6,  "name": "Classic Burger",       "category": "Mains",      "price": 16.00, "is_vegetarian": False, "is_available": True},
        {"food_id": 7,  "name": "Fish & Chips",         "category": "Mains",      "price": 18.00, "is_vegetarian": False, "is_available": True},
        {"food_id": 8,  "name": "Grilled Chicken Wrap", "category": "Mains",      "price": 14.00, "is_vegetarian": False, "is_available": True},
        {"food_id": 9,  "name": "Veggie Burger",        "category": "Mains",      "price": 15.00, "is_vegetarian": True,  "is_available": True},
        {"food_id": 10, "name": "Steak Frites",         "category": "Mains",      "price": 26.00, "is_vegetarian": False, "is_available": True},
        # Sides
        {"food_id": 11, "name": "Fries",                "category": "Sides",      "price":  6.00, "is_vegetarian": True,  "is_available": True},
        {"food_id": 12, "name": "Coleslaw",             "category": "Sides",      "price":  4.00, "is_vegetarian": True,  "is_available": True},
        {"food_id": 13, "name": "Side Salad",           "category": "Sides",      "price":  5.00, "is_vegetarian": True,  "is_available": True},
        # Desserts
        {"food_id": 14, "name": "Brownie Sundae",       "category": "Desserts",   "price": 10.00, "is_vegetarian": True,  "is_available": True},
        {"food_id": 15, "name": "Cheesecake Slice",     "category": "Desserts",   "price":  9.00, "is_vegetarian": True,  "is_available": True},
    ])

    # ── Suppliers ─────────────────────────────────────────────────────────────
    db.suppliers.insert_many([
        {"supplier_id": 1, "name": "Metro Beverage Co.",   "contact_email": "orders@metrobev.com",      "category": "Alcohol"},
        {"supplier_id": 2, "name": "Fresh Farms Produce",  "contact_email": "sales@freshfarms.com",     "category": "Food"},
        {"supplier_id": 3, "name": "Craft Spirits Direct", "contact_email": "hello@craftspirits.com",   "category": "Alcohol"},
        {"supplier_id": 4, "name": "City Meat & Seafood",  "contact_email": "info@citymeat.com",        "category": "Food"},
        {"supplier_id": 5, "name": "Paper & Supply Depot", "contact_email": "support@papersupply.com",  "category": "Supplies"},
    ])

    # ── Inventory ─────────────────────────────────────────────────────────────
    db.inventory.insert_many([
        {"item_name": "Bourbon (1L)",       "quantity": 12,  "unit": "bottles", "reorder_level":  5, "supplier_id": 1, "last_restocked": "2026-03-01"},
        {"item_name": "Tequila (1L)",       "quantity":  8,  "unit": "bottles", "reorder_level":  4, "supplier_id": 3, "last_restocked": "2026-02-20"},
        {"item_name": "Vodka (1L)",         "quantity": 15,  "unit": "bottles", "reorder_level":  5, "supplier_id": 1, "last_restocked": "2026-03-05"},
        {"item_name": "IPA Keg",            "quantity":  3,  "unit": "kegs",    "reorder_level":  2, "supplier_id": 1, "last_restocked": "2026-02-28"},
        {"item_name": "Pilsner Keg",        "quantity":  4,  "unit": "kegs",    "reorder_level":  2, "supplier_id": 1, "last_restocked": "2026-02-28"},
        {"item_name": "Chicken Wings (lb)", "quantity": 40,  "unit": "pounds",  "reorder_level": 15, "supplier_id": 4, "last_restocked": "2026-03-06"},
        {"item_name": "Ground Beef (lb)",   "quantity": 25,  "unit": "pounds",  "reorder_level": 10, "supplier_id": 4, "last_restocked": "2026-03-06"},
        {"item_name": "Limes",              "quantity": 100, "unit": "pieces",  "reorder_level": 30, "supplier_id": 2, "last_restocked": "2026-03-07"},
        {"item_name": "Napkins",            "quantity": 500, "unit": "pieces",  "reorder_level": 100,"supplier_id": 5, "last_restocked": "2026-03-01"},
        {"item_name": "Glassware (pint)",   "quantity": 80,  "unit": "pieces",  "reorder_level": 20, "supplier_id": 5, "last_restocked": "2026-02-15"},
    ])

    # ── Tabs (orders) ─────────────────────────────────────────────────────────
    db.tabs.insert_many([
        {"tab_id": 1, "customer_name": "Mike T.",        "table_number": 4,    "opened_at": "2026-03-07 18:30:00", "closed_at": "2026-03-07 20:15:00", "server_id": 5, "status": "closed"},
        {"tab_id": 2, "customer_name": "Sarah & Co.",    "table_number": 7,    "opened_at": "2026-03-07 19:00:00", "closed_at": "2026-03-07 22:00:00", "server_id": 6, "status": "closed"},
        {"tab_id": 3, "customer_name": "Bar Seat",       "table_number": None, "opened_at": "2026-03-07 21:00:00", "closed_at": "2026-03-07 23:30:00", "server_id": 1, "status": "closed"},
        {"tab_id": 4, "customer_name": "Emma R.",        "table_number": 2,    "opened_at": "2026-03-08 12:00:00", "closed_at": None,                  "server_id": 5, "status": "open"},
        {"tab_id": 5, "customer_name": "Walk-in",        "table_number": None, "opened_at": "2026-03-08 17:45:00", "closed_at": None,                  "server_id": 1, "status": "open"},
        {"tab_id": 6, "customer_name": "Birthday Party", "table_number": 10,   "opened_at": "2026-03-08 18:00:00", "closed_at": None,                  "server_id": 6, "status": "open"},
        {"tab_id": 7, "customer_name": "Alex D.",        "table_number": 3,    "opened_at": "2026-03-07 20:00:00", "closed_at": "2026-03-07 21:45:00", "server_id": 5, "status": "closed"},
        {"tab_id": 8, "customer_name": "Lisa & Mark",    "table_number": 5,    "opened_at": "2026-03-07 19:30:00", "closed_at": "2026-03-07 22:30:00", "server_id": 6, "status": "closed"},
    ])

    # ── Tab items (line items per order) ──────────────────────────────────────
    db.tab_items.insert_many([
        # Mike T. (tab 1)
        {"tab_id": 1, "item_type": "drink", "drink_id": 1,  "food_id": None, "quantity": 2, "subtotal": 28.00, "ordered_at": "2026-03-07 18:35:00"},
        {"tab_id": 1, "item_type": "food",  "drink_id": None, "food_id": 6,  "quantity": 1, "subtotal": 16.00, "ordered_at": "2026-03-07 18:40:00"},
        {"tab_id": 1, "item_type": "food",  "drink_id": None, "food_id": 11, "quantity": 1, "subtotal":  6.00, "ordered_at": "2026-03-07 18:40:00"},
        # Sarah & Co. (tab 2)
        {"tab_id": 2, "item_type": "drink", "drink_id": 3,  "food_id": None, "quantity": 3, "subtotal": 45.00, "ordered_at": "2026-03-07 19:10:00"},
        {"tab_id": 2, "item_type": "drink", "drink_id": 13, "food_id": None, "quantity": 2, "subtotal": 24.00, "ordered_at": "2026-03-07 19:10:00"},
        {"tab_id": 2, "item_type": "food",  "drink_id": None, "food_id": 1,  "quantity": 1, "subtotal": 12.00, "ordered_at": "2026-03-07 19:20:00"},
        {"tab_id": 2, "item_type": "food",  "drink_id": None, "food_id": 2,  "quantity": 1, "subtotal": 15.00, "ordered_at": "2026-03-07 19:20:00"},
        {"tab_id": 2, "item_type": "food",  "drink_id": None, "food_id": 14, "quantity": 2, "subtotal": 20.00, "ordered_at": "2026-03-07 21:00:00"},
        # Bar Seat (tab 3)
        {"tab_id": 3, "item_type": "drink", "drink_id": 7,  "food_id": None, "quantity": 3, "subtotal": 24.00, "ordered_at": "2026-03-07 21:05:00"},
        {"tab_id": 3, "item_type": "drink", "drink_id": 15, "food_id": None, "quantity": 2, "subtotal": 16.00, "ordered_at": "2026-03-07 22:00:00"},
        # Emma R. (tab 4 - open)
        {"tab_id": 4, "item_type": "drink", "drink_id": 17, "food_id": None, "quantity": 1, "subtotal":  7.00, "ordered_at": "2026-03-08 12:05:00"},
        {"tab_id": 4, "item_type": "food",  "drink_id": None, "food_id": 8,  "quantity": 1, "subtotal": 14.00, "ordered_at": "2026-03-08 12:10:00"},
        # Walk-in (tab 5 - open)
        {"tab_id": 5, "item_type": "drink", "drink_id": 1,  "food_id": None, "quantity": 1, "subtotal": 14.00, "ordered_at": "2026-03-08 17:50:00"},
        {"tab_id": 5, "item_type": "drink", "drink_id": 5,  "food_id": None, "quantity": 1, "subtotal": 14.00, "ordered_at": "2026-03-08 18:00:00"},
        # Birthday Party (tab 6 - open)
        {"tab_id": 6, "item_type": "drink", "drink_id": 3,  "food_id": None, "quantity": 6, "subtotal": 90.00, "ordered_at": "2026-03-08 18:10:00"},
        {"tab_id": 6, "item_type": "drink", "drink_id": 15, "food_id": None, "quantity": 4, "subtotal": 32.00, "ordered_at": "2026-03-08 18:15:00"},
        {"tab_id": 6, "item_type": "food",  "drink_id": None, "food_id": 1,  "quantity": 2, "subtotal": 24.00, "ordered_at": "2026-03-08 18:20:00"},
        {"tab_id": 6, "item_type": "food",  "drink_id": None, "food_id": 2,  "quantity": 2, "subtotal": 30.00, "ordered_at": "2026-03-08 18:20:00"},
        {"tab_id": 6, "item_type": "food",  "drink_id": None, "food_id": 10, "quantity": 1, "subtotal": 26.00, "ordered_at": "2026-03-08 19:00:00"},
        {"tab_id": 6, "item_type": "food",  "drink_id": None, "food_id": 14, "quantity": 3, "subtotal": 30.00, "ordered_at": "2026-03-08 20:00:00"},
        # Alex D. (tab 7)
        {"tab_id": 7, "item_type": "drink", "drink_id": 4,  "food_id": None, "quantity": 2, "subtotal": 24.00, "ordered_at": "2026-03-07 20:05:00"},
        {"tab_id": 7, "item_type": "food",  "drink_id": None, "food_id": 5,  "quantity": 1, "subtotal": 13.00, "ordered_at": "2026-03-07 20:10:00"},
        # Lisa & Mark (tab 8)
        {"tab_id": 8, "item_type": "drink", "drink_id": 11, "food_id": None, "quantity": 1, "subtotal": 11.00, "ordered_at": "2026-03-07 19:35:00"},
        {"tab_id": 8, "item_type": "drink", "drink_id": 12, "food_id": None, "quantity": 1, "subtotal": 11.00, "ordered_at": "2026-03-07 19:35:00"},
        {"tab_id": 8, "item_type": "food",  "drink_id": None, "food_id": 7,  "quantity": 1, "subtotal": 18.00, "ordered_at": "2026-03-07 19:45:00"},
        {"tab_id": 8, "item_type": "food",  "drink_id": None, "food_id": 9,  "quantity": 1, "subtotal": 15.00, "ordered_at": "2026-03-07 19:45:00"},
        {"tab_id": 8, "item_type": "food",  "drink_id": None, "food_id": 15, "quantity": 2, "subtotal": 18.00, "ordered_at": "2026-03-07 21:30:00"},
    ])

    # ── Shifts ────────────────────────────────────────────────────────────────
    db.shifts.insert_many([
        {"employee_id": 1, "shift_date": "2026-03-07", "start_time": "17:00", "end_time": "01:00", "tips_earned": 145.00},
        {"employee_id": 2, "shift_date": "2026-03-07", "start_time": "17:00", "end_time": "01:00", "tips_earned": 120.00},
        {"employee_id": 5, "shift_date": "2026-03-07", "start_time": "17:00", "end_time": "23:00", "tips_earned":  85.00},
        {"employee_id": 6, "shift_date": "2026-03-07", "start_time": "17:00", "end_time": "23:00", "tips_earned":  90.00},
        {"employee_id": 3, "shift_date": "2026-03-07", "start_time": "15:00", "end_time": "23:00", "tips_earned":   0.00},
        {"employee_id": 4, "shift_date": "2026-03-07", "start_time": "15:00", "end_time": "23:00", "tips_earned":   0.00},
        {"employee_id": 7, "shift_date": "2026-03-07", "start_time": "17:00", "end_time": "23:00", "tips_earned":  30.00},
        {"employee_id": 8, "shift_date": "2026-03-07", "start_time": "17:00", "end_time": "01:00", "tips_earned":  50.00},
        {"employee_id": 1, "shift_date": "2026-03-08", "start_time": "11:00", "end_time": "19:00", "tips_earned":  65.00},
        {"employee_id": 5, "shift_date": "2026-03-08", "start_time": "11:00", "end_time": "19:00", "tips_earned":  40.00},
        {"employee_id": 6, "shift_date": "2026-03-08", "start_time": "17:00", "end_time": "01:00", "tips_earned":   0.00},
        {"employee_id": 3, "shift_date": "2026-03-08", "start_time": "10:00", "end_time": "18:00", "tips_earned":   0.00},
        {"employee_id": 9, "shift_date": "2026-03-07", "start_time": "16:00", "end_time": "01:00", "tips_earned":   0.00},
        {"employee_id": 9, "shift_date": "2026-03-08", "start_time": "16:00", "end_time": "01:00", "tips_earned":   0.00},
    ])

    print("Bar MongoDB database created successfully.")
    return client
