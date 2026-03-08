import { useState, useEffect, useRef } from "react";

const API = (import.meta.env.VITE_QUERYBUDDY_API_URL || "http://127.0.0.1:8010").replace(/\/$/, "");

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
    PostgreSQL: { bg: "#1a3a5c", text: "#4db8ff", border: "#2a5a8c" },
    MySQL:      { bg: "#1a3a2a", text: "#4dff91", border: "#2a5a3a" },
    SQLite:     { bg: "#3a2a1a", text: "#ffaa4d", border: "#5a3a2a" },
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

function SchemaPanel({ schema, collapsed, onToggle }) {
  const [openService, setOpenService] = useState(null);

  return (
    <div style={{
      width: collapsed ? 48 : 280, minWidth: collapsed ? 48 : 280,
      background: "#0d0d0f", borderRight: "1px solid #1e1e24",
      display: "flex", flexDirection: "column", transition: "width 0.2s",
      overflow: "hidden"
    }}>
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
          <span style={{ color: "#888", fontSize: 11, fontFamily: "monospace", letterSpacing: 2, textTransform: "uppercase" }}>
            Schema Registry
          </span>
        )}
      </div>

      {!collapsed && (
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
                  {Object.entries(svc.tables).map(([tableName, cols]) => (
                    <div key={tableName} style={{ padding: "6px 14px 6px 24px" }}>
                      <div style={{ color: "#aaa", fontSize: 11, fontFamily: "monospace", marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ color: "#555" }}>▸</span>
                        <span style={{ color: "#ccc", fontWeight: 600 }}>{tableName}</span>
                      </div>
                      {cols.map(col => (
                        <div key={col.name} style={{ display: "flex", gap: 6, padding: "1px 0 1px 14px", alignItems: "center" }}>
                          {col.primary_key && <span style={{ color: "#e8c547", fontSize: 9 }}>⬡</span>}
                          {!col.primary_key && <span style={{ color: "#333", fontSize: 9 }}>·</span>}
                          <span style={{ color: "#8899aa", fontSize: 10, fontFamily: "monospace" }}>{col.name}</span>
                          <span style={{ color: "#445566", fontSize: 9, fontFamily: "monospace", marginLeft: "auto" }}>{col.type}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SqlBlock({ query }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(query.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const dbColors = {
    PostgreSQL: "#4db8ff", MySQL: "#4dff91", SQLite: "#ffaa4d"
  };

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
        fontSize: 12, lineHeight: 1.7, color: "#d4e8ff",
        whiteSpace: "pre-wrap", wordBreak: "break-word"
      }}>
        {query.sql}
      </pre>
      {query.explanation && (
        <div style={{
          padding: "8px 14px", borderTop: "1px solid #1a1a20",
          color: "#556677", fontSize: 11, fontFamily: "monospace", lineHeight: 1.5
        }}>
          {query.explanation}
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

  useEffect(() => {
    fetch(`${API}/api/schema`)
      .then(r => r.json())
      .then(setSchema)
      .catch(() => setSchema({}));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

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
        understanding: `Failed to connect to the backend. Make sure the API server is running at ${API}.`,
        queries: [], stitching_note: null, warnings: [e.message]
      }]);
    }
    setLoading(false);
  };

  const isEmpty = messages.length === 0;

  return (
    <div style={{
      display: "flex", height: "100vh", width: "100vw",
      background: "#0d0d0f", fontFamily: "'Inter', sans-serif", overflow: "hidden"
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;600&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2a2a38; border-radius: 2px; }
        textarea:focus { outline: none; }
        button:focus { outline: none; }
      `}</style>

      <SchemaPanel schema={schema} collapsed={schemaCollapsed} onToggle={() => setSchemaCollapsed(c => !c)} />

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
                  <span style={{ color: "#e8c547", fontFamily: "monospace", fontWeight: 900 }}>{ "{ QB }" }</span>
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
