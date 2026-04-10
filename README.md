# Catering Management System

A full-stack Catering Management System built with **FastAPI**, **Jinja2 + HTMX**, and **PostgreSQL (asyncpg)**. Features a dynamic pricing engine, real-time total recalculation without page reloads, and PDF bill generation.

## Features
- **Dynamic Pricing Rules**: Set tiered pricing (e.g., 1-100 plates = ₹5, 101+ = ₹4.50). 
- **HTMX Powered UI**: Search items, add to orders, and recalculate totals with zero full-page reloads.
- **PDF Generation**: Auto-generate beautifully formatted PDF bills with ReportLab.
- **Async Database**: Built entirely on Async SQLAlchemy 2.0.

## Setup Instructions

1. **Prerequisites**
   - Python 3.11+
   - PostgreSQL running locally (default expectation is on port 5432)

2. **Virtual Environment & Dependencies**
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Database Configuration**
   - Copy `.env.example` to `.env` if not already created.
   - Adjust `DATABASE_URL` in `.env` if your PostgreSQL credentials differ.

4. **Initialize Database**
   Depending on if your database is created, you may need to run:
   ```bash
   python create_db.py
   alembic upgrade head
   python catering_app/seed_data.py
   ```

5. **Run the Application**
   ```bash
   uvicorn catering_app.main:app --reload
   ```

6. **Access**
   Open your browser and navigate to `http://127.0.0.1:8000/orders`

## API Reference (Primary Endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/items` | List all menu items |
| GET | `/items/search` | (HTMX) Search items to add to order |
| GET | `/orders` | List all orders |
| POST | `/orders` | Create new draft order |
| POST | `/orders/{id}/items` | (HTMX) Add item to order |
| PUT | `/orders/{id}/plates` | (HTMX) Update plate count & recalculate |
| POST | `/bills/{order_id}` | Generate Bill record and PDF |
| GET | `/bills/{id}/pdf` | Download Bill PDF |
