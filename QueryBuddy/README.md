# QueryBuddy 🤖

> Natural language interface for microservice databases — powered by Claude.

QueryBuddy lets you query across multiple microservice databases using plain English. It understands cross-service relationships and generates accurate SQL without you needing to know the schema.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend                        │
│  • Chat UI  • Schema Browser  • SQL Display             │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                        │
│  • Schema Registry  • Claude NL2SQL  • Query Router     │
└──────┬──────────────┬──────────────┬──────────────┬─────┘
       │              │              │              │
  users.db       orders.db    products.db    payments.db
 (PostgreSQL)    (MySQL)      (PostgreSQL)   (MySQL)
```

## Mock Microservices

| Service | DB Type | Tables |
|---|---|---|
| `users_service` | PostgreSQL | users, profiles, addresses |
| `orders_service` | MySQL | orders, order_items |
| `products_service` | PostgreSQL | products, categories, inventory |
| `payments_service` | MySQL | payments, transactions |

### Cross-Service Relationships
- `orders.user_id` → `users_service.users.id`
- `order_items.product_id` → `products_service.products.id`
- `payments.order_id` → `orders_service.orders.id`

---

## Setup & Running

### Prerequisites
- Python 3.10+
- Node.js 18+
- An Anthropic API key

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
uvicorn main:app --reload --port 8000
```

The backend will automatically:
- Create and seed all 4 mock SQLite databases
- Ingest all schemas into the registry
- Start the API on http://localhost:8000

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

---

## Example Queries to Try

- *"Show me all active users"*
- *"Which orders are still pending?"*
- *"What products are low on inventory?"*
- *"Show me all completed payments"*
- *"Which users have placed more than one order?"*
- *"Show me all order items with their product names"*
- *"Find all cancelled orders and their refunded payments"*

---

## How It Works

1. **Schema Ingestion**: On startup, the backend introspects all mock databases and builds a schema registry including table structures and cross-service relationship mappings.

2. **Query Generation**: When a user sends a message, the full schema context is passed to Claude along with the question. Claude identifies the relevant services and generates SQL queries.

3. **Multi-service Queries**: For questions spanning multiple services (e.g. "show orders with user names"), Claude generates separate queries and explains how to stitch results together in application code.

4. **Conversation Memory**: The chat maintains history, so follow-up questions like "only show the active ones" work naturally.

---

## Extending for Production

To add a real database:
1. Add its connection details to `schema_registry.py` under `SERVICES`
2. Document cross-service relationships in `CROSS_SERVICE_RELATIONSHIPS`
3. Add business glossary terms to the Claude system prompt

---

*Built for hackathon demo purposes — all databases are SQLite mock files.*
