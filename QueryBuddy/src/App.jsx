import { useState, useEffect, useRef } from "react";

const API = "http://localhost:8000";

const SUGGESTED_QUERIES = [
  "Show me all active users",
  "Which orders are still pending?",
  "What products are low on inventory?",
  "Show me all completed payments",
  "Which users have placed more than one order?",
  "Show me all order items with their product names",
];

function ServiceBadge({ dbType }) {
  const colors = {
    PostgreSQL: { bg: "#1a3a5c", text: "#4db8ff",  border: "#2a5a8c" },
    MySQL:      { bg: "#1a3a2a", text: "#4dff91",  border: "#2a5a3a" },
    SQLite:     { bg: "#3a2a1a", text: "#ffaa4d",  border: "#5a3a2a" },
    MongoDB:    { bg: "#1a2a1a", text: "#6dbf67",  border: "#2a4a2a" },
  };
  const c = colors[dbType] || colors.SQLite;
  return (
    <span style={{
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
      borderRadius: 4, padding: "1px 7px", fontSize: 10, fontFamily: "monospace",
      letterSpacing: 1, textTransform: "uppercase", fontWeight: 700
    }}>{dbType}</span>
  );
}

function SchemaPanel({ schema, collapsed, onToggle, onSchemaRefresh }) {
  const [openService, setOpenService] = useState(null);
  const [showMongoForm, setShowMongoForm] = useState(false);
  const [mongoUri, setMongoUri]     = useState("mongodb://localhost:27017");
  const [mongoDb,  setMongoDb]      = useState("");
  const [mongoStatus, setMongoStatus] = useState("idle"); // idle|connecting|ok|err
  const [mongoMsg,    setMongoMsg]    = useState("");

  // Table preview state
  // previewKey: "serviceName::tableName" of the currently open preview (or null)
  // previewData: { [key]: result | "loading" | "error" }
  const [previewKey, setPreviewKey]   = useState(null);
  const [previewData, setPreviewData] = useState({});

  const toggleTablePreview = async (svcName, tableName, dbType) => {
    const key = `${svcName}::${tableName}`;
    // Collapse if already open
    if (previewKey === key) { setPreviewKey(null); return; }
    setPreviewKey(key);
    // Return cached result if already fetched
    if (previewData[key] && previewData[key] !== "loading") return;

    setPreviewData(prev => ({ ...prev, [key]: "loading" }));
    try {
      // Build query: JSON for MongoDB, SQL for everything else
      const sql = dbType === "MongoDB"
        ? JSON.stringify({ collection: tableName, operation: "find", limit: 50 })
        : `SELECT * FROM ${tableName} LIMIT 50`;

      const res  = await fetch(`${API}/api/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service: svcName, sql }),
      });
      const data = await res.json();
      setPreviewData(prev => ({ ...prev, [key]: data }));
    } catch (e) {
      setPreviewData(prev => ({ ...prev, [key]: { error: e.message } }));
    }
  };

  const connectMongo = async () => {
    if (!mongoDb.trim()) return;
    setMongoStatus("connecting");
    setMongoMsg("Connecting…");
    try {
      const res  = await fetch(`${API}/api/connect-mongo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ connection_string: mongoUri, db_name: mongoDb.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMongoStatus("err");
        setMongoMsg(data.detail || "Connection failed.");
      } else {
        setMongoStatus("ok");
        setMongoMsg(`✓ ${data.service_name} connected`);
        onSchemaRefresh();
        setTimeout(() => { setShowMongoForm(false); setMongoStatus("idle"); }, 2000);
      }
    } catch (e) {
      setMongoStatus("err");
      setMongoMsg(e.message);
    }
  };

  return (
    <div style={{
      width: collapsed ? 48 : 280, minWidth: collapsed ? 48 : 280,
      background: "#0d0d0f", borderRight: "1px solid #1e1e24",
      display: "flex", flexDirection: "column", transition: "width 0.2s",
      overflow: "hidden"
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", padding: "14px 12px",
        borderBottom: "1px solid #1e1e24", gap: 10
      }}>
        <button onClick={onToggle} style={{
          background: "none", border: "none", cursor: "pointer",
          color: "#666", fontSize: 18, lineHeight: 1, padding: 0, flexShrink: 0
        }}>
          {collapsed ? "›" : "‹"}
        </button>
        {!collapsed && (
          <span style={{ color: "#888", fontSize: 11, fontFamily: "monospace", letterSpacing: 2, textTransform: "uppercase", flex: 1 }}>
            Schema Registry
          </span>
        )}
      </div>

      {!collapsed && (
        <>
          {/* Service list */}
          <div style={{ overflowY: "auto", flex: 1, padding: "8px 0" }}>
            {Object.entries(schema).map(([svcName, svc]) => (
              <div key={svcName}>
                <button
                  onClick={() => setOpenService(openService === svcName ? null : svcName)}
                  style={{
                    width: "100%", background: openService === svcName ? "#141418" : "none",
                    border: "none", cursor: "pointer", padding: "8px 14px",
                    display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4,
                    borderLeft: openService === svcName ? "2px solid #e8c547" : "2px solid transparent",
                    transition: "all 0.15s"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
                    <span style={{ color: "#e8c547", fontSize: 11, fontFamily: "monospace", fontWeight: 700, flex: 1, textAlign: "left" }}>
                      {svcName.replace("_", "\u200B_")}
                    </span>
                    <ServiceBadge dbType={svc.db_type} />
                  </div>
                </button>
                {openService === svcName && (
                  <div style={{ padding: "4px 0 8px 0", background: "#0a0a0c" }}>
                    {Object.entries(svc.tables).map(([tableName, cols]) => {
                      const pKey    = `${svcName}::${tableName}`;
                      const isOpen  = previewKey === pKey;
                      const pResult = previewData[pKey];
                      return (
                        <div key={tableName} style={{ padding: "0 0 4px 0" }}>
                          {/* Table name row — clickable to expand data preview */}
                          <button
                            onClick={() => toggleTablePreview(svcName, tableName, svc.db_type)}
                            style={{
                              width: "100%", background: isOpen ? "#0f0f14" : "none",
                              border: "none", cursor: "pointer",
                              padding: "5px 14px 5px 24px",
                              display: "flex", alignItems: "center", gap: 6,
                              borderLeft: isOpen ? "2px solid #4db8ff" : "2px solid transparent",
                              transition: "all 0.15s",
                            }}
                          >
                            <span style={{ color: svc.db_type === "MongoDB" ? "#6dbf67" : "#4db8ff", fontSize: 9, transition: "transform 0.15s", display: "inline-block", transform: isOpen ? "rotate(90deg)" : "rotate(0deg)" }}>
                              ▶
                            </span>
                            <span style={{ color: "#ccc", fontWeight: 600, fontSize: 11, fontFamily: "monospace", flex: 1, textAlign: "left" }}>
                              {tableName}
                            </span>
                            <span style={{ color: "#334455", fontSize: 9, fontFamily: "monospace" }}>
                              {cols.length} col{cols.length !== 1 ? "s" : ""}
                            </span>
                          </button>

                          {/* Column list (shown when NOT previewing, collapsed otherwise) */}
                          {!isOpen && (
                            <div style={{ padding: "2px 0 2px 0" }}>
                              {cols.map(col => (
                                <div key={col.name} style={{ display: "flex", gap: 6, padding: "1px 14px 1px 42px", alignItems: "center" }}>
                                  {col.primary_key && <span style={{ color: "#e8c547", fontSize: 9 }}>⬡</span>}
                                  {!col.primary_key && <span style={{ color: "#333", fontSize: 9 }}>·</span>}
                                  <span style={{ color: "#8899aa", fontSize: 10, fontFamily: "monospace" }}>{col.name}</span>
                                  <span style={{ color: "#445566", fontSize: 9, fontFamily: "monospace", marginLeft: "auto" }}>{col.type}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Inline data preview */}
                          {isOpen && (
                            <div style={{ padding: "4px 10px 6px 10px" }}>
                              {pResult === "loading" || !pResult ? (
                                <div style={{ color: "#4db8ff", fontSize: 10, fontFamily: "monospace", padding: "6px 4px", opacity: 0.7 }}>
                                  Loading preview…
                                </div>
                              ) : (
                                <ResultTable result={pResult} />
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* ── Connect MongoDB footer ───────────────────────────────────── */}
          <div style={{ borderTop: "1px solid #1e1e24", padding: "10px 12px" }}>
            {!showMongoForm ? (
              <button
                onClick={() => setShowMongoForm(true)}
                style={{
                  width: "100%", background: "#0d1a0d", border: "1px solid #1a3a1a",
                  borderRadius: 6, padding: "7px 10px", cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                  color: "#6dbf67", fontSize: 11, fontFamily: "monospace", letterSpacing: 0.5,
                  transition: "all 0.15s"
                }}
                onMouseEnter={e => e.currentTarget.style.background = "#102010"}
                onMouseLeave={e => e.currentTarget.style.background = "#0d1a0d"}
              >
                <span style={{ fontSize: 14 }}>⊕</span> Connect MongoDB
              </button>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ color: "#6dbf67", fontSize: 10, fontFamily: "monospace", letterSpacing: 1 }}>
                  CONNECT MONGODB
                </div>
                <input
                  value={mongoUri}
                  onChange={e => setMongoUri(e.target.value)}
                  placeholder="mongodb://localhost:27017"
                  style={{
                    background: "#0a0a0c", border: "1px solid #2a2a38", borderRadius: 4,
                    color: "#ccd4dd", fontSize: 10, fontFamily: "monospace", padding: "5px 8px",
                    outline: "none", width: "100%"
                  }}
                />
                <input
                  value={mongoDb}
                  onChange={e => setMongoDb(e.target.value)}
                  placeholder="database name"
                  style={{
                    background: "#0a0a0c", border: "1px solid #2a2a38", borderRadius: 4,
                    color: "#ccd4dd", fontSize: 10, fontFamily: "monospace", padding: "5px 8px",
                    outline: "none", width: "100%"
                  }}
                />
                {mongoMsg && (
                  <div style={{
                    fontSize: 10, fontFamily: "monospace", padding: "3px 0",
                    color: mongoStatus === "ok" ? "#4dff91" : mongoStatus === "err" ? "#ff6b6b" : "#6dbf67"
                  }}>{mongoMsg}</div>
                )}
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    onClick={connectMongo}
                    disabled={mongoStatus === "connecting" || !mongoDb.trim()}
                    style={{
                      flex: 1, background: mongoStatus === "connecting" ? "#1e1e28" : "#6dbf67",
                      border: "none", borderRadius: 4, padding: "5px 0",
                      color: "#0d0d0f", fontFamily: "monospace", fontSize: 10, fontWeight: 700,
                      cursor: mongoStatus === "connecting" ? "not-allowed" : "pointer", letterSpacing: 0.5
                    }}
                  >
                    {mongoStatus === "connecting" ? "CONNECTING…" : "CONNECT"}
                  </button>
                  <button
                    onClick={() => { setShowMongoForm(false); setMongoStatus("idle"); setMongoMsg(""); }}
                    style={{
                      background: "none", border: "1px solid #2a2a38", borderRadius: 4,
                      padding: "5px 10px", color: "#556677", fontFamily: "monospace",
                      fontSize: 10, cursor: "pointer"
                    }}
                  >
                    ✕
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function downloadCsv(columns, rows, filename = "querybuddy_results.csv") {
  const escape = (val) => {
    if (val === null || val === undefined) return "";
    const s = String(val);
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  };
  const header = columns.map(escape).join(",");
  const body = rows.map(row => row.map(escape).join(",")).join("\n");
  const csv = header + "\n" + body;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function ResultTable({ result }) {
  if (!result || result.error) {
    return (
      <div style={{
        padding: "10px 14px", background: "#1a0a0a", border: "1px solid #3a1a1a",
        borderRadius: 6, marginTop: 8, color: "#ff6b6b", fontSize: 11, fontFamily: "monospace"
      }}>
        Error: {result?.error || "Unknown error"}
      </div>
    );
  }
  if (!result.columns || result.columns.length === 0) {
    return (
      <div style={{
        padding: "10px 14px", background: "#0a0f0a", border: "1px solid #1a2a1a",
        borderRadius: 6, marginTop: 8, color: "#4dff91", fontSize: 11, fontFamily: "monospace"
      }}>
        Query executed successfully. Rows affected: {result.rows_affected ?? 0}
      </div>
    );
  }
  return (
    <div style={{
      marginTop: 8, border: "1px solid #1e1e28", borderRadius: 6,
      overflow: "auto", maxHeight: 300
    }}>
      <table style={{
        width: "100%", borderCollapse: "collapse", fontSize: 11,
        fontFamily: "'JetBrains Mono', monospace"
      }}>
        <thead>
          <tr>
            {result.columns.map((col, i) => (
              <th key={i} style={{
                padding: "8px 12px", background: "#111118", color: "#8899aa",
                borderBottom: "1px solid #1e1e28", textAlign: "left",
                position: "sticky", top: 0, fontWeight: 600, fontSize: 10,
                letterSpacing: 0.5, textTransform: "uppercase"
              }}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.length === 0 ? (
            <tr>
              <td colSpan={result.columns.length} style={{
                padding: "12px", color: "#556677", textAlign: "center",
                fontStyle: "italic"
              }}>No rows returned</td>
            </tr>
          ) : result.rows.map((row, ri) => (
            <tr key={ri} style={{ background: ri % 2 === 0 ? "#0a0a0c" : "#0d0d10" }}>
              {row.map((cell, ci) => (
                <td key={ci} style={{
                  padding: "6px 12px", color: "#ccd4dd",
                  borderBottom: "1px solid #141418", whiteSpace: "nowrap"
                }}>{cell === null ? <span style={{ color: "#445" }}>NULL</span> : String(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{
        padding: "6px 12px", background: "#0a0a0c", borderTop: "1px solid #1e1e28",
        color: "#445566", fontSize: 10, fontFamily: "monospace",
        display: "flex", alignItems: "center", justifyContent: "space-between"
      }}>
        <span>{result.rows.length} row{result.rows.length !== 1 ? "s" : ""}</span>
        {result.rows.length > 0 && (
          <button
            onClick={() => downloadCsv(result.columns, result.rows)}
            style={{
              background: "none", border: "1px solid #2a2a38", borderRadius: 4,
              color: "#667788", fontSize: 9, cursor: "pointer",
              padding: "2px 8px", fontFamily: "monospace", letterSpacing: 0.5,
              transition: "all 0.15s"
            }}
            onMouseEnter={e => { e.currentTarget.style.color = "#4db8ff"; e.currentTarget.style.borderColor = "#4db8ff"; }}
            onMouseLeave={e => { e.currentTarget.style.color = "#667788"; e.currentTarget.style.borderColor = "#2a2a38"; }}
          >
            CSV
          </button>
        )}
      </div>
    </div>
  );
}

function SqlBlock({ query, onExecute }) {
  const [copied, setCopied] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [writeResult, setWriteResult] = useState(null);

  // Short-circuit: render a dimmed "skipped" card when the backend flagged
  // this query as skipped due to an empty upstream result.
  if (query.skipped) {
    return (
      <div style={{
        background: "#0d0d10", border: "1px dashed #2a2a38",
        borderRadius: 8, marginTop: 10, padding: "12px 16px",
        display: "flex", alignItems: "center", gap: 10, opacity: 0.6
      }}>
        <span style={{
          background: "#1a1a24", color: "#556677", border: "1px solid #2a2a38",
          borderRadius: 4, padding: "1px 7px", fontSize: 9,
          fontFamily: "monospace", letterSpacing: 1, fontWeight: 700
        }}>SKIPPED</span>
        <span style={{ color: "#445566", fontSize: 11, fontFamily: "monospace" }}>
          {query.service}
        </span>
        <span style={{ color: "#334455", fontSize: 11, flex: 1 }}>
          {query.skip_reason}
        </span>
      </div>
    );
  }

  const copy = () => {
    navigator.clipboard.writeText(query.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleExecute = async () => {
    setExecuting(true);
    try {
      const res = await fetch(`${API}/api/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service: query.service, sql: query.sql })
      });
      const data = await res.json();
      setWriteResult(data);
    } catch (e) {
      setWriteResult({ error: e.message });
    }
    setExecuting(false);
  };

  const dbColors = {
    PostgreSQL: "#4db8ff", MySQL: "#4dff91", SQLite: "#ffaa4d", MongoDB: "#6dbf67"
  };

  // For MongoDB services the "sql" field is actually a JSON object —
  // detect and pretty-print it so it renders as formatted JSON, not a flat string.
  const isMongo = query.db_type === "MongoDB";
  const displaySql = (() => {
    if (!isMongo) return query.sql;
    try { return JSON.stringify(JSON.parse(query.sql), null, 2); }
    catch { return query.sql; }
  })();

  // Bug 8 fix: treat a query as read-only ONLY when is_read is explicitly true.
  // The old `!== false` defaulted unset fields to true, which could have caused
  // a write query to render as AUTO-RUN if the backend omitted the field.
  const isRead = query.is_read === true;

  return (
    <div style={{
      background: "#0a0a0c", border: "1px solid #1e1e28",
      borderRadius: 8, marginTop: 10, overflow: "hidden"
    }}>
      <div style={{
        display: "flex", alignItems: "center", padding: "8px 14px",
        background: "#111116", borderBottom: "1px solid #1e1e28", gap: 8
      }}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%",
          background: dbColors[query.db_type] || "#666", flexShrink: 0
        }} />
        <span style={{ color: "#888", fontSize: 11, fontFamily: "monospace", flex: 1 }}>
          {query.service}
        </span>
        {isRead && (
          <span style={{
            background: "#0a1a0a", color: "#4dff91", border: "1px solid #1a3a1a",
            borderRadius: 4, padding: "1px 7px", fontSize: 9, fontFamily: "monospace",
            letterSpacing: 1, fontWeight: 700
          }}>AUTO-RUN</span>
        )}
        {!isRead && (
          <span style={{
            background: "#1a0a0a", color: "#ff6b6b", border: "1px solid #3a1a1a",
            borderRadius: 4, padding: "1px 7px", fontSize: 9, fontFamily: "monospace",
            letterSpacing: 1, fontWeight: 700
          }}>WRITE</span>
        )}
        <ServiceBadge dbType={query.db_type} />
        <button onClick={copy} style={{
          background: "none", border: "1px solid #333", borderRadius: 4,
          color: copied ? "#4dff91" : "#666", fontSize: 10, cursor: "pointer",
          padding: "2px 8px", fontFamily: "monospace", letterSpacing: 1
        }}>
          {copied ? "COPIED" : "COPY"}
        </button>
      </div>
      <pre style={{
        margin: 0, padding: "14px 16px", overflowX: "auto",
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
        fontSize: 12, lineHeight: 1.7, color: isMongo ? "#a8d5a2" : "#d4e8ff",
        whiteSpace: "pre-wrap", wordBreak: "break-word"
      }}>
        {displaySql}
      </pre>
      {query.explanation && (
        <div style={{
          padding: "8px 14px", borderTop: "1px solid #1a1a20",
          color: "#556677", fontSize: 11, fontFamily: "monospace", lineHeight: 1.5
        }}>
          {query.explanation}
        </div>
      )}

      {/* Show auto-executed read results */}
      {isRead && query.result && (
        <div style={{ padding: "0 14px 14px 14px" }}>
          <ResultTable result={query.result} />
        </div>
      )}

      {/* Show execute button for write queries */}
      {!isRead && !writeResult && (
        <div style={{
          padding: "10px 14px", borderTop: "1px solid #1a1a20",
          display: "flex", alignItems: "center", gap: 10
        }}>
          <button
            onClick={handleExecute}
            disabled={executing}
            style={{
              background: executing ? "#1e1e28" : "#e8c547",
              border: "none", borderRadius: 6, padding: "6px 16px",
              color: executing ? "#666" : "#0d0d0f", fontSize: 11,
              fontFamily: "monospace", fontWeight: 700, letterSpacing: 1,
              cursor: executing ? "not-allowed" : "pointer",
              transition: "all 0.15s"
            }}
          >
            {executing ? "EXECUTING..." : "EXECUTE"}
          </button>
          <span style={{ color: "#ff6b6b", fontSize: 10, fontFamily: "monospace" }}>
            This will modify the database
          </span>
        </div>
      )}

      {/* Show write query results */}
      {!isRead && writeResult && (
        <div style={{ padding: "0 14px 14px 14px" }}>
          <ResultTable result={writeResult} />
        </div>
      )}
    </div>
  );
}

function AssistantMessage({ msg }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: "90%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{
          width: 24, height: 24, borderRadius: "50%", background: "#e8c547",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 11, fontWeight: 900, color: "#0d0d0f", flexShrink: 0
        }}>Q</div>
        <span style={{ color: "#e8c547", fontSize: 11, fontFamily: "monospace", letterSpacing: 1 }}>QUERYBUDDY</span>
      </div>

      <div style={{ paddingLeft: 32 }}>
        <p style={{ color: "#ccd4dd", fontSize: 13, lineHeight: 1.6, margin: "0 0 8px 0" }}>
          {msg.understanding}
        </p>

        {msg.queries && msg.queries.map((q, i) => <SqlBlock key={i} query={q} />)}

        {msg.stitching_note && (
          <div style={{
            marginTop: 10, padding: "10px 14px", background: "#111420",
            border: "1px solid #1e2840", borderRadius: 8, borderLeft: "3px solid #4db8ff"
          }}>
            <div style={{ color: "#4db8ff", fontSize: 10, fontFamily: "monospace", letterSpacing: 1, marginBottom: 4 }}>
              ▸ APPLICATION STITCHING
            </div>
            <p style={{ color: "#8899bb", fontSize: 12, margin: 0, lineHeight: 1.6 }}>
              {msg.stitching_note}
            </p>
          </div>
        )}

        {msg.warnings && msg.warnings.length > 0 && (
          <div style={{
            marginTop: 10, padding: "10px 14px", background: "#141008",
            border: "1px solid #2a2010", borderRadius: 8, borderLeft: "3px solid #e8c547"
          }}>
            <div style={{ color: "#e8c547", fontSize: 10, fontFamily: "monospace", letterSpacing: 1, marginBottom: 4 }}>
              ⚠ NOTES
            </div>
            {msg.warnings.map((w, i) => (
              <p key={i} style={{ color: "#998866", fontSize: 12, margin: "2px 0", lineHeight: 1.5 }}>
                {w}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function UserMessage({ text }) {
  return (
    <div style={{ display: "flex", justifyContent: "flex-end" }}>
      <div style={{
        background: "#1a1a24", border: "1px solid #2a2a38",
        borderRadius: "12px 12px 2px 12px", padding: "10px 16px",
        maxWidth: "70%", color: "#dde8f0", fontSize: 13, lineHeight: 1.5
      }}>
        {text}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, paddingLeft: 32 }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 6, height: 6, borderRadius: "50%", background: "#e8c547",
          animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`
        }} />
      ))}
      <style>{`@keyframes pulse { 0%,80%,100%{opacity:0.2;transform:scale(0.8)} 40%{opacity:1;transform:scale(1)} }`}</style>
    </div>
  );
}

export default function App() {
  const [schema, setSchema] = useState({});
  const [schemaCollapsed, setSchemaCollapsed] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiHistory, setApiHistory] = useState([]);
  const bottomRef = useRef(null);

  // ── Drag-and-drop state ────────────────────────────────────────────────────
  const [isDragging, setIsDragging] = useState(false);
  // "idle" | "uploading" | "success" | "error"
  const [uploadStatus, setUploadStatus] = useState("idle");
  const [uploadMessage, setUploadMessage] = useState("");
  // Counter trick: dragLeave fires for every child element, so we count
  // enter/leave events and only hide the overlay when the count reaches 0.
  const dragCounter = useRef(0);

  const refreshSchema = () =>
    fetch(`${API}/api/schema`)
      .then(r => r.json())
      .then(setSchema)
      .catch(() => {});

  useEffect(() => { refreshSchema(); }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // ── Drag handlers ──────────────────────────────────────────────────────────
  const handleDragEnter = (e) => {
    e.preventDefault();
    dragCounter.current++;
    setIsDragging(true);
  };
  const handleDragOver = (e) => { e.preventDefault(); };
  const handleDragLeave = (e) => {
    e.preventDefault();
    dragCounter.current--;
    if (dragCounter.current === 0) setIsDragging(false);
  };
  const handleDrop = async (e) => {
    e.preventDefault();
    dragCounter.current = 0;
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (!file) return;

    setUploadStatus("uploading");
    setUploadMessage(`Uploading ${file.name}…`);

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/api/upload-db`, { method: "POST", body: form });
      const data = await res.json();

      if (!res.ok) {
        setUploadStatus("error");
        setUploadMessage(data.detail || "Upload failed.");
      } else {
        const tableCount = Object.keys(data.schema?.tables || {}).length;
        setUploadStatus("success");
        setUploadMessage(
          `✓ ${data.service_name} registered — ${tableCount} table${tableCount !== 1 ? "s" : ""} available`
        );
        refreshSchema();
      }
    } catch (err) {
      setUploadStatus("error");
      setUploadMessage(`Upload failed: ${err.message}`);
    }

    // Auto-dismiss the status overlay after 3 s
    setTimeout(() => setUploadStatus("idle"), 3000);
  };

  const send = async (text) => {
    if (!text.trim() || loading) return;
    const userText = text.trim();
    setInput("");
    setMessages(m => [...m, { type: "user", text: userText }]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText, history: apiHistory })
      });
      const data = await res.json();
      setMessages(m => [...m, { type: "assistant", ...data }]);
      setApiHistory(h => [
        ...h,
        { role: "user", content: userText },
        { role: "assistant", content: JSON.stringify(data) }
      ]);
    } catch (e) {
      setMessages(m => [...m, {
        type: "assistant",
        understanding: "Failed to connect to the backend. Make sure the API server is running on port 8000.",
        queries: [], stitching_note: null, warnings: [e.message]
      }]);
    }
    setLoading(false);
  };

  const isEmpty = messages.length === 0;

  return (
    <div
      style={{
        display: "flex", height: "100vh", width: "100vw",
        background: "#0d0d0f", fontFamily: "'Inter', sans-serif", overflow: "hidden",
        position: "relative",
      }}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;600&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2a2a38; border-radius: 2px; }
        textarea:focus { outline: none; }
        button:focus { outline: none; }
        @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
      `}</style>

      {/* ── Drag-and-drop overlay ─────────────────────────────────────────── */}
      {(isDragging || uploadStatus !== "idle") && (
        <div style={{
          position: "absolute", inset: 0, zIndex: 100,
          background: "rgba(13,13,15,0.92)",
          backdropFilter: "blur(6px)",
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", gap: 20,
          border: `2px dashed ${
            uploadStatus === "error" ? "#ff6b6b"
            : uploadStatus === "success" ? "#4dff91"
            : "#e8c547"
          }`,
          animation: "fadeIn 0.15s ease",
          pointerEvents: isDragging ? "all" : "none",
        }}>
          {/* Icon */}
          <div style={{ fontSize: 52, lineHeight: 1 }}>
            {uploadStatus === "uploading" ? "⏳"
              : uploadStatus === "success" ? "✅"
              : uploadStatus === "error" ? "❌"
              : "🗄️"}
          </div>

          {/* Primary label */}
          <div style={{
            color: uploadStatus === "error" ? "#ff6b6b"
              : uploadStatus === "success" ? "#4dff91"
              : "#e8c547",
            fontFamily: "monospace", fontSize: 18, fontWeight: 700, letterSpacing: 1,
          }}>
            {uploadStatus === "uploading" ? "UPLOADING…"
              : uploadStatus === "success" ? "DATABASE ADDED"
              : uploadStatus === "error" ? "UPLOAD FAILED"
              : "DROP DATABASE FILE"}
          </div>

          {/* Sub-label */}
          <div style={{
            color: "#556677", fontFamily: "monospace", fontSize: 12, letterSpacing: 0.5,
            maxWidth: 420, textAlign: "center", lineHeight: 1.6,
          }}>
            {uploadStatus !== "idle"
              ? uploadMessage
              : "Drop a .db · .sqlite · .sqlite3 file to register it as a new queryable service"}
          </div>
        </div>
      )}

      <SchemaPanel schema={schema} collapsed={schemaCollapsed} onToggle={() => setSchemaCollapsed(c => !c)} onSchemaRefresh={refreshSchema} />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <div style={{
          padding: "14px 24px", borderBottom: "1px solid #1e1e24",
          display: "flex", alignItems: "center", gap: 14, background: "#0d0d0f"
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, background: "#e8c547",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, fontWeight: 900, color: "#0d0d0f"
          }}>Q</div>
          <div>
            <div style={{ color: "#dde8f0", fontSize: 15, fontWeight: 600, letterSpacing: 0.5 }}>QueryBuddy</div>
            <div style={{ color: "#556677", fontSize: 11, fontFamily: "monospace" }}>
              {Object.keys(schema).length} services · {Object.values(schema).reduce((acc, s) => acc + Object.keys(s.tables || {}).length, 0)} tables
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            {Object.values(schema).map((s, i) => (
              <div key={i} style={{
                width: 8, height: 8, borderRadius: "50%",
                background: ["#4db8ff","#4dff91","#ffaa4d","#ff6b6b"][i] || "#666"
              }} title={Object.keys(schema)[i]} />
            ))}
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "24px", display: "flex", flexDirection: "column", gap: 24 }}>
          {isEmpty && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 32 }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 40, marginBottom: 12 }}>
                  <span style={{ color: "#e8c547", fontFamily: "monospace", fontWeight: 900 }}>{ "{ QBuddy }" }</span>
                </div>
                <div style={{ color: "#445566", fontSize: 13, fontFamily: "monospace" }}>
                  Ask anything about your microservice data
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", maxWidth: 560 }}>
                {SUGGESTED_QUERIES.map((q, i) => (
                  <button key={i} onClick={() => send(q)} style={{
                    background: "#111116", border: "1px solid #1e1e28", borderRadius: 20,
                    color: "#778899", fontSize: 12, padding: "7px 14px", cursor: "pointer",
                    fontFamily: "monospace", transition: "all 0.15s",
                    letterSpacing: 0.3
                  }}
                  onMouseEnter={e => { e.target.style.borderColor = "#e8c547"; e.target.style.color = "#e8c547"; }}
                  onMouseLeave={e => { e.target.style.borderColor = "#1e1e28"; e.target.style.color = "#778899"; }}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i}>
              {msg.type === "user" ? <UserMessage text={msg.text} /> : <AssistantMessage msg={msg} />}
            </div>
          ))}
          {loading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ padding: "16px 24px", borderTop: "1px solid #1e1e24", background: "#0d0d0f" }}>
          <div style={{
            display: "flex", gap: 10, background: "#111116",
            border: "1px solid #2a2a38", borderRadius: 12, padding: "10px 14px",
            alignItems: "flex-end"
          }}>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }}}
              placeholder="Ask about your data... (Enter to send, Shift+Enter for newline)"
              rows={1}
              style={{
                flex: 1, background: "none", border: "none", color: "#dde8f0",
                fontSize: 13, lineHeight: 1.5, resize: "none", fontFamily: "inherit",
                maxHeight: 120, overflowY: "auto"
              }}
              onInput={e => {
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
              }}
            />
            <button
              onClick={() => send(input)}
              disabled={loading || !input.trim()}
              style={{
                background: loading || !input.trim() ? "#1e1e28" : "#e8c547",
                border: "none", borderRadius: 8, width: 34, height: 34,
                cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 16, color: loading || !input.trim() ? "#444" : "#0d0d0f",
                transition: "all 0.15s", flexShrink: 0, fontWeight: 700
              }}
            >
              ↑
            </button>
          </div>
          <div style={{ color: "#2a3a4a", fontSize: 10, fontFamily: "monospace", marginTop: 6, textAlign: "center", letterSpacing: 1 }}>
            QUERYBUDDY · HACKATHON DEMO · ANTHROPIC CLAUDE
          </div>
        </div>
      </div>
    </div>
  );
}
