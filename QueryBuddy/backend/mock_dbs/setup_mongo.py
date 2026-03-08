"""
Mock MongoDB setup using mongomock (in-memory, no server required).

Creates an 'analytics_service' with two collections:
  - events   : page views, clicks, add-to-cart etc., keyed by user_id
  - sessions : browsing sessions keyed by user_id

user_ids match users_service so cross-service queries work.
"""

try:
    import mongomock
    MONGOMOCK_AVAILABLE = True
except ImportError:
    MONGOMOCK_AVAILABLE = False

# Module-level client kept alive for the process lifetime
_analytics_client = None


def get_analytics_client():
    return _analytics_client


def setup_analytics_mongo():
    global _analytics_client

    if not MONGOMOCK_AVAILABLE:
        print("mongomock not installed — skipping MongoDB mock (run: pip install mongomock)")
        return None

    _analytics_client = mongomock.MongoClient()
    db = _analytics_client["analytics"]

    # Drop first so re-running setup_all() stays idempotent
    db.events.drop()
    db.sessions.drop()

    db.events.insert_many([
        {"user_id": 1, "type": "page_view",   "page": "/home",      "timestamp": "2024-01-15T10:00:00", "duration_ms": 1200},
        {"user_id": 1, "type": "click",        "element": "buy_button",   "product_id": 1, "timestamp": "2024-01-15T10:05:00"},
        {"user_id": 1, "type": "add_to_cart",  "product_id": 2,      "timestamp": "2024-01-16T09:15:00"},
        {"user_id": 1, "type": "page_view",    "page": "/products",  "timestamp": "2024-01-16T09:00:00", "duration_ms": 2100},
        {"user_id": 2, "type": "page_view",    "page": "/products",  "timestamp": "2024-01-15T11:00:00", "duration_ms": 3400},
        {"user_id": 2, "type": "page_view",    "page": "/checkout",  "timestamp": "2024-01-15T11:10:00", "duration_ms": 800},
        {"user_id": 2, "type": "click",        "element": "checkout_btn", "timestamp": "2024-01-15T11:12:00"},
        {"user_id": 3, "type": "page_view",    "page": "/home",      "timestamp": "2024-01-15T12:00:00", "duration_ms": 500},
    ])

    db.sessions.insert_many([
        {"user_id": 1, "session_id": "sess_001", "started_at": "2024-01-15T10:00:00", "ended_at": "2024-01-15T10:30:00", "page_count": 3, "device": "desktop"},
        {"user_id": 2, "session_id": "sess_002", "started_at": "2024-01-15T11:00:00", "ended_at": "2024-01-15T11:20:00", "page_count": 2, "device": "mobile"},
        {"user_id": 3, "session_id": "sess_003", "started_at": "2024-01-15T12:00:00", "ended_at": "2024-01-15T12:05:00", "page_count": 1, "device": "mobile"},
        {"user_id": 1, "session_id": "sess_004", "started_at": "2024-01-16T09:00:00", "ended_at": "2024-01-16T09:45:00", "page_count": 4, "device": "desktop"},
    ])

    print("Analytics MongoDB mock created successfully.")
    return _analytics_client
