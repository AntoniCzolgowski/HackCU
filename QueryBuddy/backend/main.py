from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mock_dbs.setup_databases import setup_all
from mock_dbs.setup_mongo import setup_analytics_mongo
from schema_registry import (
    get_full_registry, build_schema_context,
    is_read_query, is_schema_modifying_query, execute_query,
    register_dynamic_service, register_mongo_service, BASE_DIR,
)
from claude_service import generate_sql

# SQLite files always start with this 16-byte header
SQLITE_MAGIC = b"SQLite format 3\x00"

app = FastAPI(title="QueryBuddy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize on startup
registry = {}
schema_context = ""

@app.on_event("startup")
def startup():
    global registry, schema_context
    # SQLite mock services
    setup_all()
    # MongoDB mock service (in-memory via mongomock — no server needed)
    mongo_client = setup_analytics_mongo()
    if mongo_client:
        register_mongo_service(
            service_name="analytics_service",
            client=mongo_client,
            db_name="analytics",
            description="User behaviour analytics — events and sessions (MongoDB)",
        )
    registry = get_full_registry()
    schema_context = build_schema_context(registry)
    print("QueryBuddy ready.")

# ---- Models ----

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class QueryRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []

class ExecuteRequest(BaseModel):
    service: str
    sql: str

class MongoConnectRequest(BaseModel):
    connection_string: str   # e.g. "mongodb://localhost:27017"
    db_name: str             # database to expose
    service_name: Optional[str] = None  # auto-derived if omitted

# ---- Routes ----

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/schema")
def get_schema():
    return registry

MAX_MESSAGE_LENGTH = 4000  # characters

@app.post("/api/query")
def query(req: QueryRequest):
    # Bug 6 fix: validate message length and content
    msg = req.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(msg) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Message too long ({len(msg)} chars). Maximum is {MAX_MESSAGE_LENGTH}."
        )

    history = [{"role": m.role, "content": m.content} for m in req.history]

    # Schema context is now always injected via the system prompt in
    # generate_sql (Bug 2 fix), so we no longer need the if/else split here.
    result = generate_sql(msg, schema_context, history)

    # Auto-execute read queries and attach results.
    # Short-circuit: if multiple queries are chained (stitching_note is set)
    # and the first query returns 0 rows, skip the rest — they would filter
    # on IDs that don't exist and return misleading data.
    queries = result.get("queries", [])
    is_chained = bool(result.get("stitching_note"))
    upstream_empty = False

    for i, q in enumerate(queries):
        q["is_read"] = is_read_query(q.get("sql", ""))

        if is_chained and upstream_empty and i > 0:
            q["skipped"] = True
            q["skip_reason"] = (
                "Skipped: the upstream query returned 0 rows, so this query "
                "would produce no meaningful results."
            )
            continue

        if q["is_read"]:
            q["result"] = execute_query(q["service"], q["sql"])
            # Mark upstream empty only for the first query in a chain
            if i == 0 and is_chained:
                rows = q["result"].get("rows")
                if rows is not None and len(rows) == 0:
                    upstream_empty = True

    return result


@app.post("/api/connect-mongo")
def connect_mongo(req: MongoConnectRequest):
    """
    Connect to a real (or mongomock) MongoDB instance, register it as a live
    service, and rebuild the schema context so Claude knows about its collections.
    """
    global registry, schema_context

    try:
        import pymongo
        client = pymongo.MongoClient(req.connection_string, serverSelectionTimeoutMS=5000)
        # Force a connection attempt to surface errors early
        client.server_info()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot connect to MongoDB: {e}")

    # Derive a unique service name
    base_name = re.sub(r'[^a-z0-9]+', '_', req.db_name.lower()).strip('_')
    base_service = (req.service_name or base_name) + "_service"
    service_name = base_service
    counter = 2
    while service_name in registry:
        service_name = f"{base_name}_{counter}_service"
        counter += 1

    register_mongo_service(
        service_name=service_name,
        client=client,
        db_name=req.db_name,
        description=f"MongoDB: {req.db_name} @ {req.connection_string}",
    )
    registry = get_full_registry()
    schema_context = build_schema_context(registry)

    return {"service_name": service_name, "schema": registry[service_name]}


@app.post("/api/upload-db")
async def upload_db(file: UploadFile = File(...)):
    """
    Accept a drag-and-dropped SQLite database file, validate it, save it to
    mock_dbs/, register it as a live service, and rebuild the schema context
    so Claude immediately knows about the new tables.
    """
    global registry, schema_context

    # ── 1. Extension check ────────────────────────────────────────────────────
    filename = file.filename or ""
    if not re.search(r'\.(db|sqlite|sqlite3)$', filename, re.IGNORECASE):
        raise HTTPException(
            status_code=400,
            detail="Only .db, .sqlite, or .sqlite3 files are accepted."
        )

    # ── 2. Read & magic-byte check ────────────────────────────────────────────
    content = await file.read()
    if not content.startswith(SQLITE_MAGIC):
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be a valid SQLite database."
        )

    # ── 3. Derive a unique service name from the filename ─────────────────────
    stem = re.sub(r'\.(db|sqlite|sqlite3)$', '', filename, flags=re.IGNORECASE)
    base_name = re.sub(r'[^a-z0-9]+', '_', stem.lower()).strip('_')
    base_service = base_name + "_service"

    # Avoid collisions with existing services
    service_name = base_service
    counter = 2
    while service_name in registry:
        service_name = f"{base_name}_{counter}_service"
        counter += 1

    # ── 4. Save to mock_dbs/ ──────────────────────────────────────────────────
    db_path = os.path.join(BASE_DIR, f"{service_name}.db")
    with open(db_path, "wb") as f:
        f.write(content)

    # ── 5. Register & rebuild schema ──────────────────────────────────────────
    register_dynamic_service(service_name, db_path)
    registry = get_full_registry()
    schema_context = build_schema_context(registry)

    return {
        "service_name": service_name,
        "schema": registry[service_name],
    }


@app.post("/api/execute")
def execute(req: ExecuteRequest):
    # Prompt 17 fix: allow user-approved DML (INSERT/UPDATE/DELETE) but reject
    # schema-modifying DDL (DROP/CREATE/ALTER/TRUNCATE) which is irreversible.
    # The original Bug 7 fix was too broad — it blocked all non-SELECT including
    # legitimate UPDATE statements the user explicitly clicked EXECUTE on.
    if is_schema_modifying_query(req.sql):
        raise HTTPException(
            status_code=400,
            detail=(
                "Schema-modifying operations (DROP, CREATE, ALTER, TRUNCATE) "
                "are not permitted via this endpoint."
            )
        )
    return execute_query(req.service, req.sql)
