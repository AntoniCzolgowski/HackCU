# QueryBuddy — Edge Case & Bug Report

> Analyzed and fixed March 2026.
> All 8 bugs below have been patched in the codebase.

---

## How QueryBuddy Works (Quick Summary)

QueryBuddy is a natural-language-to-SQL chatbot backed by FastAPI + Claude.
A user types a plain-English question → Claude generates SQL → the backend auto-executes read queries against four SQLite mock databases (users, orders, products, payments) → results are shown in the UI.

---

## Bug 1 — Wrong `from_service` in Cross-Service Relationships

**File:** `backend/schema_registry.py` · **Severity: High**

### What breaks
The `CROSS_SERVICE_RELATIONSHIPS` list had `"from_service": "order_items"` for the order_items → products link.  `order_items` is a *table*, not a service.  The correct service is `orders_service`.

Claude reads this list to understand cross-service joins.  When asked "show me all order items with their product names," Claude would see a broken relationship mapping and either generate wrong SQL or produce a confusing stitching note.

### Fix
```python
# Before
{"from_service": "order_items", ...}
# After
{"from_service": "orders_service", ...}
```

---

## Bug 2 — Schema Context Disappears After the First Turn

**File:** `backend/claude_service.py` · **Severity: Critical**

### What breaks
The database schema (table names, column names, types) was injected only into the *first* user message.  On subsequent turns the frontend stored history as plain user text with no schema attached.  Claude's follow-up API calls therefore had **zero schema context**, so questions like "only show the active ones" could generate hallucinated column names or wrong table references.

Reproduce: ask two questions in a row.  The second answer frequently references columns or tables incorrectly.

### Fix
Move the schema context from an ad-hoc user-message injection into the **system prompt**, which is sent on every API call regardless of history length.  The system prompt is augmented at call-time:

```python
augmented_system = SYSTEM_PROMPT + "\n\n" + schema_context
response = client.messages.create(system=augmented_system, ...)
```

---

## Bug 3 — `is_read_query` Bypassed by Write-Inside-CTE

**File:** `backend/schema_registry.py` · **Severity: High (Security)**

### What breaks
`is_read_query` checked only the *first keyword* of a statement.  Because `WITH` was whitelisted (needed for legitimate CTEs), a malicious or hallucinated query like:

```sql
WITH cte AS (DELETE FROM users RETURNING *) SELECT * FROM cte
```

passed the check and was auto-executed as if it were a harmless SELECT.

### Fix
After confirming the first keyword is safe (`SELECT`, `WITH`, `EXPLAIN`), a secondary scan checks the entire cleaned statement for any DML/DDL keyword using word-boundary regex:

```python
WRITE_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|UPSERT|MERGE|ATTACH|DETACH)\b',
    re.IGNORECASE
)
if WRITE_KEYWORDS.search(cleaned):
    return False
```

The regex uses `\b` word boundaries so column names like `deleted_at` or `created_by` do not trigger a false positive.

---

## Bug 4 — Fragile Markdown Fence Stripping

**File:** `backend/claude_service.py` · **Severity: Medium**

### What breaks
The old stripping logic was:
```python
if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]
```

Claude typically returns ` ```json\n{...}\n``` `.  After `split("```")[1]` the result is `json\n{...}\n`.  The check `raw.startswith("json")` is True, stripping `"json"` — but the leading newline remains.  `json.loads("\n{...}")` usually succeeds, but edge cases like trailing text after the closing fence, or a fence with no language tag followed by newline, caused `JSONDecodeError`.

### Fix
Replaced with a robust helper `_strip_markdown_fences` that:
1. Drops the entire opening fence line (everything up to and including the first `\n`)
2. Strips the closing ` ``` ` if present
3. Calls `.strip()` to remove any surrounding whitespace

---

## Bug 5 — Unbounded Conversation History Causes Token Limit Failures

**File:** `backend/claude_service.py` · **Severity: Medium**

### What breaks
`apiHistory` on the frontend grows with every message.  Because each API call sends the full history, a long session (10–20+ exchanges) eventually exceeds Claude's context window or becomes extremely slow and costly.

### Fix
Cap history at `MAX_HISTORY_TURNS = 10` pairs (20 messages) before building the messages array:

```python
capped_history = conversation_history[-(MAX_HISTORY_TURNS * 2):]
```

---

## Bug 6 — No Input Validation on User Messages

**File:** `backend/main.py` · **Severity: Medium**

### What breaks
The `/api/query` endpoint accepted any string, including empty strings (which were already blocked on the frontend but not the API) and strings of arbitrary length.  A 100 000-character message would be sent directly to Claude, potentially blowing the token budget or causing slow responses.

### Fix
```python
MAX_MESSAGE_LENGTH = 4000

msg = req.message.strip()
if not msg:
    raise HTTPException(status_code=400, detail="Message cannot be empty.")
if len(msg) > MAX_MESSAGE_LENGTH:
    raise HTTPException(status_code=400, detail=f"Message too long ...")
```

---

## Bug 7 — `/api/execute` Allowed Arbitrary Destructive SQL

**File:** `backend/main.py` · **Severity: High (Security)**

### What breaks
The `/api/execute` endpoint was supposed to be used by the frontend's "EXECUTE" button on write queries (INSERT/UPDATE/DELETE generated by Claude).  However, the endpoint performed **no read-only check** — any caller could POST:

```json
{ "service": "users_service", "sql": "DROP TABLE users" }
```

and it would be executed immediately.

### Fix
Enforce `is_read_query` at the endpoint level and return HTTP 400 for anything that is not a SELECT.  If write operations are needed in the future, they should be handled behind an explicit confirmation mechanism and proper authentication.

```python
if not is_read_query(req.sql):
    raise HTTPException(status_code=400, detail="Only SELECT queries are allowed via this endpoint.")
```

---

## Bug 8 — Frontend `is_read` Defaulted to `true` When Field Was Missing

**File:** `src/App.jsx` · **Severity: Low–Medium**

### What breaks
```javascript
const isRead = query.is_read !== false;  // old code
```

If the backend ever omitted `is_read` from a query object (e.g. during a parsing error fallback or future API change), `undefined !== false` evaluates to `true`, causing the UI to display the query as AUTO-RUN and attempt to render results — even for a write query.

### Fix
```javascript
const isRead = query.is_read === true;  // explicit equality
```

---

## Additional Edge Cases (Lower Risk, No Code Change Required)

| # | Description | Observed Behavior |
|---|---|---|
| A | Question about non-existent data (`"show me premium users"`) | Claude returns empty queries with a warning — handled gracefully |
| B | Hallucinated service name (`"analytics_service"`) | `execute_query` returns `{"error": "Unknown service: ..."}` — displayed as red error in UI |
| C | Empty result set from a valid query | UI shows "No rows returned" — handled gracefully |
| D | Question entirely outside the schema (`"what is the weather?"`) | Claude returns empty queries + explanation — handled gracefully |
| E | Very large result sets (e.g. `SELECT * FROM users` on millions of rows) | No row limit is enforced; could cause slow UI renders. **Recommendation:** add `LIMIT 500` to auto-executed queries. |
| F | Concurrent requests from same session | No server-side session locking; results could interleave. Acceptable for a single-user demo. |

---

## Summary Table

| # | File | Severity | Status |
|---|---|---|---|
| 1 | `schema_registry.py` | High | ✅ Fixed |
| 2 | `claude_service.py` | Critical | ✅ Fixed |
| 3 | `schema_registry.py` | High | ✅ Fixed |
| 4 | `claude_service.py` | Medium | ✅ Fixed |
| 5 | `claude_service.py` | Medium | ✅ Fixed |
| 6 | `main.py` | Medium | ✅ Fixed |
| 7 | `main.py` | High | ✅ Fixed |
| 8 | `src/App.jsx` | Low–Medium | ✅ Fixed |
