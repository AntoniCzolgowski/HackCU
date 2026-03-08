import sqlite3
import json
import os
import re

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_dbs")

# ── SQL services (SQLite files labelled as their real-world db_type) ──────────
SERVICES = {
    "users_service": {
        "description": "Manages user accounts, profiles, and addresses",
        "db_type": "PostgreSQL",
        "db_path": os.path.join(BASE_DIR, "users.db"),
    },
    "orders_service": {
        "description": "Handles customer orders and line items",
        "db_type": "MySQL",
        "db_path": os.path.join(BASE_DIR, "orders.db"),
    },
    "products_service": {
        "description": "Manages product catalog, categories, and inventory",
        "db_type": "PostgreSQL",
        "db_path": os.path.join(BASE_DIR, "products.db"),
    },
    "payments_service": {
        "description": "Processes payments and transaction records",
        "db_type": "MySQL",
        "db_path": os.path.join(BASE_DIR, "payments.db"),
    },
}

# ── MongoDB clients: service_name → live pymongo / mongomock client ───────────
MONGO_CLIENTS: dict = {}

CROSS_SERVICE_RELATIONSHIPS = [
    {
        "from_service": "orders_service",
        "from_table": "orders",
        "from_column": "user_id",
        "to_service": "users_service",
        "to_table": "users",
        "to_column": "id",
        "description": "An order belongs to a user"
    },
    {
        "from_service": "orders_service",
        "from_table": "order_items",
        "from_column": "product_id",
        "to_service": "products_service",
        "to_table": "products",
        "to_column": "id",
        "description": "An order item references a product"
    },
    {
        "from_service": "payments_service",
        "from_table": "payments",
        "from_column": "order_id",
        "to_service": "orders_service",
        "to_table": "orders",
        "to_column": "id",
        "description": "A payment is associated with an order"
    },
]


# ── Dynamic registration ──────────────────────────────────────────────────────

def register_dynamic_service(service_name: str, db_path: str, db_type: str = "SQLite", description: str = "") -> None:
    """Hot-register a new SQLite service at runtime (drag-and-drop upload)."""
    SERVICES[service_name] = {
        "description": description or f"Dynamically loaded database: {os.path.basename(db_path)}",
        "db_type": db_type,
        "db_path": db_path,
    }


def register_mongo_service(service_name: str, client, db_name: str, description: str = "") -> None:
    """Register a MongoDB service (mongomock or real pymongo client)."""
    SERVICES[service_name] = {
        "description": description or f"MongoDB database: {db_name}",
        "db_type": "MongoDB",
        "db_name": db_name,
    }
    MONGO_CLIENTS[service_name] = client


# ── Schema introspection ──────────────────────────────────────────────────────

def _get_sql_schema(service_name: str) -> dict:
    service = SERVICES[service_name]
    conn = sqlite3.connect(service["db_path"])
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in c.fetchall()]
    schema = {}
    for table in tables:
        c.execute(f"PRAGMA table_info({table})")
        schema[table] = [
            {"name": col[1], "type": col[2], "nullable": not col[3], "primary_key": bool(col[5])}
            for col in c.fetchall()
        ]
    conn.close()
    return schema


def _get_mongo_schema(service_name: str) -> dict:
    """Infer MongoDB collection schemas by sampling documents."""
    client = MONGO_CLIENTS.get(service_name)
    if not client:
        return {}
    service = SERVICES[service_name]
    db = client[service["db_name"]]
    schema = {}
    for coll_name in sorted(db.list_collection_names()):
        sample = list(db[coll_name].find({}, {"_id": 0}).limit(20))
        fields_seen: dict = {}
        for doc in sample:
            for key, val in doc.items():
                if key not in fields_seen:
                    fields_seen[key] = type(val).__name__
        schema[coll_name] = [
            {"name": k, "type": v, "nullable": True, "primary_key": False}
            for k, v in fields_seen.items()
        ]
    return schema


def get_schema_for_service(service_name: str) -> dict:
    service = SERVICES[service_name]
    if service["db_type"] == "MongoDB":
        return _get_mongo_schema(service_name)
    return _get_sql_schema(service_name)


def get_full_registry() -> dict:
    registry = {}
    for service_name, service_info in SERVICES.items():
        schema = get_schema_for_service(service_name)
        registry[service_name] = {
            "description": service_info["description"],
            "db_type": service_info["db_type"],
            "tables": schema,
        }
    return registry


# ── Schema context for Claude ─────────────────────────────────────────────────

def build_schema_context(registry: dict) -> str:
    lines = ["=== DATABASE SCHEMA REGISTRY ===\n"]
    for service_name, service in registry.items():
        lines.append(f"SERVICE: {service_name} ({service['db_type']})")
        lines.append(f"Description: {service['description']}")
        # Use TABLE for SQL, COLLECTION for MongoDB
        label = "COLLECTION" if service["db_type"] == "MongoDB" else "TABLE"
        for table_name, columns in service["tables"].items():
            lines.append(f"  {label}: {table_name}")
            for col in columns:
                pk = " [PK]" if col["primary_key"] else ""
                nullable = "" if col["nullable"] else " NOT NULL"
                lines.append(f"    - {col['name']}: {col['type']}{pk}{nullable}")
        lines.append("")

    lines.append("=== CROSS-SERVICE RELATIONSHIPS ===")
    for rel in CROSS_SERVICE_RELATIONSHIPS:
        lines.append(
            f"  {rel['from_service']}.{rel['from_table']}.{rel['from_column']} "
            f"→ {rel['to_service']}.{rel['to_table']}.{rel['to_column']} "
            f"({rel['description']})"
        )
    return "\n".join(lines)


# ── Query guards ──────────────────────────────────────────────────────────────

def is_read_query(sql: str) -> bool:
    """
    Returns True if the query is safe to auto-execute (read-only).
    Handles both SQL strings and MongoDB JSON query objects.
    """
    stripped = sql.strip()

    # ── MongoDB JSON query ────────────────────────────────────────────────────
    if stripped.startswith("{"):
        try:
            q = json.loads(stripped)
            op = str(q.get("operation", "find")).lower()
            return op in ("find", "aggregate", "count", "findone")
        except json.JSONDecodeError:
            return False

    # ── SQL ───────────────────────────────────────────────────────────────────
    cleaned = re.sub(r'--[^\n]*', '', stripped)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    if not cleaned:
        return False

    first_word = cleaned.split()[0].upper()
    if first_word not in ("SELECT", "WITH", "EXPLAIN"):
        return False

    WRITE_KEYWORDS = re.compile(
        r'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|UPSERT|MERGE|ATTACH|DETACH)\b',
        re.IGNORECASE
    )
    return not bool(WRITE_KEYWORDS.search(cleaned))


def is_schema_modifying_query(sql: str) -> bool:
    """
    Returns True if the SQL/query is a schema-modifying DDL operation that
    should never be executed via the UI execute button.
    MongoDB queries are always considered non-schema-modifying here (they go
    through execute_query which limits to find/aggregate/count anyway).
    """
    stripped = sql.strip()
    if stripped.startswith("{"):
        return False  # MongoDB: handled by execute_mongo_query's op whitelist

    cleaned = re.sub(r'--[^\n]*', '', stripped)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    if not cleaned:
        return True
    DANGEROUS_DDL = re.compile(
        r'\b(DROP|CREATE|ALTER|TRUNCATE|ATTACH|DETACH)\b',
        re.IGNORECASE
    )
    return bool(DANGEROUS_DDL.search(cleaned))


# ── Query execution ───────────────────────────────────────────────────────────

def _execute_sql_query(service_name: str, sql: str) -> dict:
    service = SERVICES[service_name]
    conn = sqlite3.connect(service["db_path"])
    try:
        c = conn.cursor()
        c.execute(sql)
        if is_read_query(sql):
            columns = [desc[0] for desc in c.description] if c.description else []
            rows = [list(row) for row in c.fetchall()]
            return {"columns": columns, "rows": rows}
        else:
            conn.commit()
            return {"rows_affected": c.rowcount}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


def _execute_mongo_query(service_name: str, query_str: str) -> dict:
    """Execute a MongoDB JSON query object. Only find / aggregate / count allowed."""
    client = MONGO_CLIENTS.get(service_name)
    if not client:
        return {"error": "No MongoDB connection available for this service."}

    try:
        query = json.loads(query_str)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid MongoDB query JSON: {e}"}

    collection_name = query.get("collection")
    if not collection_name:
        return {"error": "MongoDB query must specify a 'collection' field."}

    operation = str(query.get("operation", "find")).lower()
    service = SERVICES[service_name]
    db = client[service["db_name"]]

    try:
        available = db.list_collection_names()
    except Exception as e:
        return {"error": f"Cannot list collections: {e}"}

    if collection_name not in available:
        return {"error": f"Collection '{collection_name}' not found. Available: {available}"}

    collection = db[collection_name]

    try:
        if operation == "find":
            filter_   = query.get("filter", {})
            projection = query.get("projection", {})
            projection["_id"] = 0          # always exclude ObjectId
            sort  = query.get("sort")
            limit = min(query.get("limit", 100), 500)
            cursor = collection.find(filter_, projection)
            if sort:
                cursor = cursor.sort(sort)
            docs = list(cursor.limit(limit))

        elif operation == "aggregate":
            pipeline = query.get("pipeline", [])
            docs = list(collection.aggregate(pipeline))
            for d in docs:
                d.pop("_id", None)

        elif operation == "count":
            count = collection.count_documents(query.get("filter", {}))
            return {"columns": ["count"], "rows": [[count]]}

        else:
            return {
                "error": (
                    f"Unsupported MongoDB operation '{operation}'. "
                    "Supported: find, aggregate, count."
                )
            }

        if not docs:
            return {"columns": [], "rows": []}

        columns = list(docs[0].keys())
        rows = [
            [str(doc.get(col)) if doc.get(col) is not None else None for col in columns]
            for doc in docs
        ]
        return {"columns": columns, "rows": rows}

    except Exception as e:
        return {"error": str(e)}


def execute_query(service_name: str, sql: str) -> dict:
    """Route to SQL or MongoDB execution based on the service's db_type."""
    if service_name not in SERVICES:
        return {"error": f"Unknown service: {service_name}"}
    if SERVICES[service_name]["db_type"] == "MongoDB":
        return _execute_mongo_query(service_name, sql)
    return _execute_sql_query(service_name, sql)
