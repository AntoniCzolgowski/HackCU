import { useMemo, useState } from "react";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { BusinessDetailResponse, BusinessMatchComparison, MatchMeta, MetricFilterKey, OpportunityBoardResponse } from "../lib/types";
import { formatCompact, titleCase } from "../lib/format";

interface BusinessDrawerProps {
  detail: BusinessDetailResponse | null;
  comparison: BusinessMatchComparison | null;
  opportunityBoard: OpportunityBoardResponse | null;
  match: MatchMeta;
  isLoading: boolean;
  metricFilters: Record<MetricFilterKey, boolean>;
  onToggleMetricFilter: (key: MetricFilterKey) => void;
  onJumpToStep: (day: number, step: number) => void;
  onGenerateReport: () => void;
  reportState: { isGenerating: boolean; status: string | null };
}

type DemandChartRow = {
  step: number;
  label: string;
  axisLabel: string;
  value: number;
  marker?: string | null;
  fill: string;
};

function markerLabel(marker: string | null | undefined) {
  if (!marker) return "";
  return marker.replace(/_/g, " ");
}

function buildDemandChartRows(detail: BusinessDetailResponse | null): DemandChartRow[] {
  if (!detail) return [];

  const isMatchDay = detail.day === 0;
  const series = detail.active_visitors_series_15m;
  const markerSteps = new Set(series.filter((point) => point.marker).map((point) => point.step));
  markerSteps.add(detail.peak.step);

  const kickoffStep = series.find((point) => point.marker === "kickoff")?.step ?? detail.peak.step;
  const finalWhistleStep = series.find((point) => point.marker === "final_whistle")?.step ?? detail.peak.step;

  return series
    .filter((point) => point.step % 4 === 0 || markerSteps.has(point.step))
    .map((point) => {
      let fill = "#38BDF8";
      if (isMatchDay && point.step >= kickoffStep && point.step <= finalWhistleStep) {
        fill = "#F97316";
      } else if (isMatchDay && point.step > finalWhistleStep) {
        fill = "#F59E0B";
      }

      return {
        step: point.step,
        label: point.label,
        axisLabel: point.step % 8 === 0 ? point.label : "",
        value: point.value,
        marker: point.marker,
        fill,
      };
    });
}

/* ── Staffing Calculator ────────────────────────────── */
const STAFF_RATIOS: Record<string, number> = {
  restaurant: 1 / 12,
  sports_bar: 1 / 15,
  cocktail_bar: 1 / 10,
  hotel_bar: 1 / 12,
  hotel: 1 / 20,
};

function buildStaffingPlan(detail: BusinessDetailResponse) {
  const ratio = STAFF_RATIOS[detail.business.type] ?? 1 / 14;
  const series = detail.active_visitors_series_15m;
  const hours: { label: string; staff: number; peak: number }[] = [];
  for (let i = 0; i < series.length; i += 4) {
    const chunk = series.slice(i, i + 4);
    const peak = Math.max(...chunk.map((p) => p.value));
    const staff = Math.max(1, Math.ceil(peak * ratio));
    hours.push({ label: chunk[0].label, staff, peak });
  }
  return hours;
}

/* ── Inventory Prep Guide ───────────────────────────── */
const DRINK_RATIOS: Record<string, number> = { restaurant: 1.2, sports_bar: 2.5, cocktail_bar: 2.0, hotel_bar: 1.8, hotel: 0.8 };
const FOOD_RATIOS: Record<string, number> = { restaurant: 0.85, sports_bar: 0.4, cocktail_bar: 0.2, hotel_bar: 0.3, hotel: 0.5 };
const BEER_SHARE: Record<string, number> = { restaurant: 0.5, sports_bar: 0.7, cocktail_bar: 0.3, hotel_bar: 0.4, hotel: 0.4 };

function buildInventoryGuide(detail: BusinessDetailResponse, match: MatchMeta) {
  const visitors = detail.served_visits_today;
  const type = detail.business.type;
  const totalDrinks = Math.ceil(visitors * (DRINK_RATIOS[type] ?? 1.5));
  const totalFood = Math.ceil(visitors * (FOOD_RATIOS[type] ?? 0.5));
  const beerPct = BEER_SHARE[type] ?? 0.5;
  const beers = Math.ceil(totalDrinks * beerPct);
  const cocktails = Math.ceil(totalDrinks * (1 - beerPct - 0.15));
  const softDrinks = totalDrinks - beers - cocktails;
  const waterBottles = Math.ceil(visitors * 0.6);

  const mix = detail.nationality_mix;
  const dominant = Object.entries(mix).sort((a, b) => b[1] - a[1])[0];
  const dominantLabel = dominant[0] === "team_a" ? match.home_team.name : dominant[0] === "team_b" ? match.away_team.name : dominant[0] === "locals" ? "local" : "neutral";

  return { totalDrinks, totalFood, beers, cocktails, softDrinks, waterBottles, dominantLabel };
}

/* ── CSV Export ──────────────────────────────────────── */
function downloadCSV(detail: BusinessDetailResponse, match: MatchMeta) {
  const header = "Time,Active Visitors,Marker\n";
  const rows = detail.active_visitors_series_15m.map((p) => `${p.label},${p.value},${p.marker ?? ""}`).join("\n");
  const summary =
    `\n\nSummary\nVenue,"${detail.business.name}"\nType,${detail.business.type}\n` +
    `Match,"${match.title}"\nServed Visits,${detail.served_visits_today}\n` +
    `Revenue Estimate,$${detail.served_revenue.total}\nPeak Time,${detail.peak.label}\n` +
    `Peak Visitors,${detail.peak_active_visitors}\nPeak Capacity %,${detail.peak_capacity_pct_capped}\n`;
  const blob = new Blob([header + rows + summary], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${detail.business.name.replace(/\s+/g, "_")}_matchflow.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function ExplanationPanel({
  metricKey,
  detail,
}: {
  metricKey: string;
  detail: BusinessDetailResponse;
}) {
  const explanation = detail.metric_explanations[metricKey];
  if (!explanation) return null;
  return (
    <div className="metric-explanation-shell">
      <button type="button" className="info-button" aria-label={`Explain ${explanation.title}`}>
        ?
      </button>
      <div className="metric-explanation-popover" role="tooltip">
        <strong>{explanation.title}</strong>
        <p>{explanation.definition}</p>
        <code>{explanation.formula}</code>
        <div className="metric-input-list">
          {Object.entries(explanation.inputs).map(([key, value]) => (
            <span key={key}>
              {titleCase(key)}: {String(value)}
            </span>
          ))}
        </div>
        {explanation.notes.map((note) => (
          <small key={note}>{note}</small>
        ))}
      </div>
    </div>
  );
}

export function BusinessDrawer({
  detail,
  comparison,
  opportunityBoard,
  match,
  isLoading,
  metricFilters,
  onToggleMetricFilter,
  onJumpToStep,
  onGenerateReport,
  reportState,
}: BusinessDrawerProps) {
  const demandChartRows = useMemo(() => buildDemandChartRows(detail), [detail]);
  const isMatchDay = detail?.day === 0;
  const [boardSort, setBoardSort] = useState<"score" | "revenue" | "risk">("score");

  const fanMixRows = useMemo(() => {
    if (!detail) return [];
    const labels: Record<string, string> = {
      team_a: match.home_team.name,
      team_b: match.away_team.name,
      neutral: "Neutral",
      locals: "Locals",
    };
    const colors: Record<string, string> = {
      team_a: match.home_team.color,
      team_b: match.away_team.color,
      neutral: "#38BDF8",
      locals: "#94A3B8",
    };
    return Object.entries(detail.nationality_mix).map(([key, value]) => ({
      key,
      label: labels[key] ?? titleCase(key),
      value,
      color: colors[key] ?? "#94A3B8",
    }));
  }, [detail, match.away_team.color, match.away_team.name, match.home_team.color, match.home_team.name]);

  const staffingPlan = useMemo(() => (detail ? buildStaffingPlan(detail) : []), [detail]);
  const inventoryGuide = useMemo(() => (detail ? buildInventoryGuide(detail, match) : null), [detail, match]);

  const sortedBoardMatches = useMemo(() => {
    if (!opportunityBoard?.matches.length) return [];
    const matches = [...opportunityBoard.matches];
    if (boardSort === "revenue") matches.sort((a, b) => b.revenue_estimate - a.revenue_estimate);
    else if (boardSort === "risk") matches.sort((a, b) => b.score_breakdown.risk_index - a.score_breakdown.risk_index);
    else matches.sort((a, b) => b.opportunity_score - a.opportunity_score);
    return matches;
  }, [opportunityBoard, boardSort]);

  if (!detail && !isLoading) {
    return (
      <aside className="panel drawer">
        <div className="section-header">
          <h2>Venue intelligence</h2>
        </div>
        <p className="empty-state">Select a business marker or a watchlist row to open a live venue playbook.</p>
      </aside>
    );
  }

  if (!detail || isLoading) {
    return (
      <aside className="panel drawer">
        <div className="section-header">
          <h2>Venue intelligence</h2>
        </div>
        <div className="drawer-loading-shell">
          <div className="drawer-loading-bar" />
          <p>Loading business analytics, comparisons, and recommendation report context.</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="panel drawer">
      <div className="section-header">
        <div>
          <h2>{detail.business.name}</h2>
          <p className="drawer-subtitle">
            {titleCase(detail.business.type)} | {detail.zone_context.zone_name} | {detail.google_rating.value.toFixed(1)} stars
          </p>
        </div>
      </div>

      {/* ── Capacity Alert Banner ────────────────────── */}
      {detail.peak_capacity_pct_capped >= 100 && (
        <div className="capacity-alert-banner danger fade-in-up">
          <strong>Capacity warning</strong>
          <span>
            Projected to reach {detail.peak_capacity_pct_capped}% at {detail.peak.label}.
            {detail.peak_capacity_pct_capped >= 120
              ? " Expect queues and spillover. Simplify menu and add queue management."
              : " Plan for busy-hour staffing and fast service."}
          </span>
        </div>
      )}
      {detail.peak_capacity_pct_capped >= 85 && detail.peak_capacity_pct_capped < 100 && (
        <div className="capacity-alert-banner warning fade-in-up">
          <strong>Heads up</strong>
          <span>
            Projected to reach {detail.peak_capacity_pct_capped}% capacity at {detail.peak.label}. Prepare for a busy window.
          </span>
        </div>
      )}

      <div className="metric-filter-row">
        {(Object.keys(metricFilters) as MetricFilterKey[]).map((key) => (
          <button
            key={key}
            type="button"
            className={metricFilters[key] ? "chip active" : "chip"}
            onClick={() => onToggleMetricFilter(key)}
          >
            {titleCase(key)}
          </button>
        ))}
      </div>

      <div className="drawer-toolbar">
        <button type="button" className="compact-chip" onClick={() => onJumpToStep(detail.day, detail.peak.step)}>
          Jump to my peak
        </button>
        <button type="button" className="compact-chip" onClick={onGenerateReport} disabled={reportState.isGenerating}>
          {reportState.isGenerating ? "Generating PDF..." : "Generate PDF report"}
        </button>
        <button type="button" className="compact-chip" onClick={() => downloadCSV(detail, match)}>
          Export CSV
        </button>
        {reportState.status ? <span className="stat-footnote">Report: {reportState.status}</span> : null}
      </div>

      <div className="insight-grid">
        {detail.insight_cards.map((card, index) => (
          <article key={card.label} className={`insight-card tone-${card.tone} fade-in-up`} style={{ animationDelay: `${index * 60}ms` }}>
            <div className={`insight-card-top ${index % 2 === 0 ? "popover-anchor-left" : "popover-anchor-right"}`}>
              <span>{card.label}</span>
              <ExplanationPanel metricKey={card.metric_key} detail={detail} />
            </div>
            <strong title={card.detail}>{card.value}</strong>
            <small>{card.detail}</small>
          </article>
        ))}
      </div>

      {metricFilters.capacity ? (
        <div className="capacity-gauge-section">
          <div className="chart-header">
            <h3>Peak capacity</h3>
            <ExplanationPanel metricKey="peak_capacity" detail={detail} />
          </div>
          <div className="capacity-gauge-bar">
            <div
              className="capacity-gauge-fill animated-fill"
              style={{
                width: `${Math.min(detail.peak_capacity_pct_capped / 1.5, 100)}%`,
                background: detail.peak_capacity_pct_capped >= 120 ? "#F43F5E" : detail.peak_capacity_pct_capped >= 85 ? "#F97316" : "#22C55E",
              }}
            />
          </div>
          <div className="capacity-gauge-labels">
            <span>{detail.peak_capacity_pct_capped}% at peak</span>
            <span>{detail.peak_capacity_pct_capped >= 120 ? "Over capacity - expect queues" : detail.peak_capacity_pct_capped >= 85 ? "Busy operating window" : "Healthy headroom"} | 150% display cap</span>
          </div>
        </div>
      ) : null}

      {/* ── Staffing Calculator ──────────────────────── */}
      {metricFilters.capacity && staffingPlan.length > 0 ? (
        <div className="chart-card fade-in-up">
          <h3>Staffing calculator</h3>
          <p className="chart-footnote">Recommended staff count per hour based on peak visitor load and venue type ratio (1:{Math.round(1 / (STAFF_RATIOS[detail.business.type] ?? 1 / 14))}).</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={staffingPlan} margin={{ top: 8, right: 8, left: -16, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#203046" />
              <XAxis dataKey="label" stroke="#cbd5e1" tickLine={false} axisLine={false} interval={1} tick={{ fontSize: 10 }} angle={-45} textAnchor="end" height={48} />
              <YAxis stroke="#cbd5e1" tickLine={false} axisLine={false} width={32} tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ borderRadius: 14, border: "1px solid rgba(148, 163, 184, 0.25)", background: "#ffffff", color: "#0f172a", boxShadow: "0 16px 40px rgba(15, 23, 42, 0.18)" }}
                formatter={(value) => [`${Number(value ?? 0)} staff`, "Recommended"]}
              />
              <Bar dataKey="staff" radius={[6, 6, 0, 0]} maxBarSize={18}>
                {staffingPlan.map((row, i) => (
                  <Cell key={i} fill={row.staff >= Math.ceil(detail.business.capacity_estimate * (STAFF_RATIOS[detail.business.type] ?? 1 / 14) * 0.8) ? "#F97316" : "#38BDF8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="staffing-summary">
            <span>Peak: <strong>{Math.max(...staffingPlan.map((h) => h.staff))} staff</strong> at {staffingPlan.reduce((a, b) => (b.staff > a.staff ? b : a)).label}</span>
            <span>Min: <strong>{Math.min(...staffingPlan.map((h) => h.staff))} staff</strong> during off-peak</span>
          </div>
        </div>
      ) : null}

      {metricFilters.demand ? (
        <div className="chart-card">
          <div className="chart-header">
            <h3>Active visitors over time</h3>
            <ExplanationPanel metricKey="active_visitors" detail={detail} />
          </div>
          <p className="chart-footnote">
            {isMatchDay
              ? "Readable hourly view from the canonical 15-minute model. Marker lines keep kickoff, halftime, final whistle, and peak visible."
              : "Readable hourly view from the canonical 15-minute model. Peak remains visible without match-phase overlays on non-match days."}
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={demandChartRows} margin={{ top: 14, right: 8, left: -16, bottom: 18 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#203046" />
              <XAxis
                dataKey="label"
                stroke="#cbd5e1"
                tickLine={false}
                axisLine={false}
                interval={0}
                height={58}
                tick={{ fontSize: 11 }}
                angle={-45}
                textAnchor="end"
                tickMargin={10}
                tickFormatter={(_value, index) => demandChartRows[index]?.axisLabel ?? ""}
              />
              <YAxis stroke="#cbd5e1" tickLine={false} axisLine={false} width={48} tick={{ fontSize: 11 }} />
              <Tooltip
                cursor={{ fill: "rgba(148, 163, 184, 0.08)" }}
                contentStyle={{
                  borderRadius: 14,
                  border: "1px solid rgba(148, 163, 184, 0.25)",
                  background: "#ffffff",
                  color: "#0f172a",
                  boxShadow: "0 16px 40px rgba(15, 23, 42, 0.18)",
                }}
                formatter={(value) => [`${Number(value ?? 0).toLocaleString()} active visitors`, "Demand"]}
                labelFormatter={(label) => `Time ${String(label ?? "")}`}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={22}>
                {demandChartRows.map((row) => (
                  <Cell key={row.step} fill={row.fill} />
                ))}
              </Bar>
              {detail.active_visitors_series_15m
                .filter((point) => point.step === detail.peak.step || (isMatchDay && point.marker))
                .map((point) => (
                  <ReferenceLine
                    key={`${point.step}-${point.marker ?? "peak"}`}
                    x={point.label}
                    stroke={point.marker === "peak" || point.step === detail.peak.step ? "#F43F5E" : "#F97316"}
                    strokeDasharray="4 4"
                    label={{ value: markerLabel(point.marker ?? "peak"), position: "top", fill: "#cbd5e1", fontSize: 10 }}
                  />
                ))}
            </BarChart>
          </ResponsiveContainer>
          {isMatchDay ? (
            <div className="chart-phase-legend">
              <span><i style={{ background: "#38BDF8" }} />Pre-match</span>
              <span><i style={{ background: "#F97316" }} />In-match</span>
              <span><i style={{ background: "#F59E0B" }} />Post-match</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {metricFilters.revenue ? (
        <article className="recommendation-card revenue-card fade-in-up">
          <p className="eyebrow">Revenue estimate</p>
          <strong>${detail.served_revenue.total.toLocaleString()}</strong>
          <p>
            Based on {detail.served_revenue.served_visits_today} served visits x ${detail.served_revenue.avg_spend.toFixed(0)} average spend x {Math.round(detail.served_revenue.service_capture_rate * 100)}% capture rate.
          </p>
        </article>
      ) : null}

      {/* ── Inventory Prep Guide ─────────────────────── */}
      {metricFilters.revenue && inventoryGuide ? (
        <article className="recommendation-card fade-in-up" style={{ animationDelay: "80ms" }}>
          <p className="eyebrow">Inventory prep guide</p>
          <div className="inventory-grid">
            <div className="inventory-item">
              <strong>{inventoryGuide.beers.toLocaleString()}</strong>
              <span>Beers</span>
            </div>
            <div className="inventory-item">
              <strong>{inventoryGuide.cocktails.toLocaleString()}</strong>
              <span>Cocktails</span>
            </div>
            <div className="inventory-item">
              <strong>{inventoryGuide.softDrinks.toLocaleString()}</strong>
              <span>Soft drinks</span>
            </div>
            <div className="inventory-item">
              <strong>{inventoryGuide.waterBottles.toLocaleString()}</strong>
              <span>Water bottles</span>
            </div>
            <div className="inventory-item">
              <strong>{inventoryGuide.totalFood.toLocaleString()}</strong>
              <span>Food portions</span>
            </div>
            <div className="inventory-item">
              <strong>{detail.served_visits_today.toLocaleString()}</strong>
              <span>Expected visitors</span>
            </div>
          </div>
          <p className="fan-mix-insight" style={{ marginTop: 10 }}>
            Dominant fan group: {inventoryGuide.dominantLabel}. Bias beer selection and menu specials toward this audience.
          </p>
        </article>
      ) : null}

      {metricFilters.demand ? (
        <div className="chart-card">
          <h3>3-day demand window</h3>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={detail.day_comparison}>
              <XAxis dataKey="label" stroke="#94a3b8" tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} hide />
              <Tooltip />
              <Bar dataKey="served_visits_today" radius={[6, 6, 0, 0]}>
                {detail.day_comparison.map((row) => (
                  <Cell key={row.day} fill={row.day === 0 ? "#F97316" : "#38BDF8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      {metricFilters.audience ? (
        <div className="chart-card">
          <h3>Audience mix</h3>
          <div className="fan-mix-list">
            {fanMixRows.map((row) => (
              <div key={row.key} className="fan-mix-row">
                <span className="fan-mix-label">
                  <i className="fan-mix-dot" style={{ background: row.color }} />
                  {row.label}
                </span>
                <div className="fan-mix-bar-shell">
                  <div className="fan-mix-bar animated-fill" style={{ width: `${row.value}%`, background: row.color }} />
                </div>
                <strong>{row.value}%</strong>
              </div>
            ))}
          </div>
          <p className="fan-mix-insight">
            Dominant group: {detail.audience_profile.dominant_label} ({detail.audience_profile.dominant_share}%). This should drive menu, signage, and staffing tone.
          </p>
        </div>
      ) : null}

      {metricFilters.recommendations ? (
        <>
          <article className="recommendation-card">
            <p className="eyebrow">Owner recommendation | {detail.recommendation.source}</p>
            <p>{detail.recommendation.text}</p>
          </article>
          <article className="recommendation-card">
            <p className="eyebrow">Operational playbook</p>
            <div className="action-list">
              {detail.playbook.action_options.map((action) => (
                <div key={action.title} className="action-item">
                  <div className="action-header">
                    <strong>{action.title}</strong>
                    <span className={`priority-badge priority-${action.priority}`}>{action.priority}</span>
                    <span className="timing-badge">{action.timing}</span>
                  </div>
                  <p>{action.detail}</p>
                </div>
              ))}
            </div>
          </article>
        </>
      ) : null}

      {/* ── Opportunity Board ────────────────────────── */}
      {metricFilters.competition && opportunityBoard && opportunityBoard.matches.length > 0 ? (
        <div className="chart-card board-card fade-in-up">
          <div className="chart-header">
            <h3>Consulting Opportunity Board</h3>
          </div>
          <div className="board-kpi-strip">
            <div className="board-kpi glow-accent">
              <span>Best Match</span>
              <strong>{opportunityBoard.matches.find((m) => m.match_id === opportunityBoard.portfolio_summary.best_match_id)?.title ?? "—"}</strong>
            </div>
            <div className="board-kpi">
              <span>Avg Score</span>
              <strong>{opportunityBoard.portfolio_summary.avg_opportunity_score}</strong>
            </div>
            <div className="board-kpi">
              <span>Volatility</span>
              <strong>{opportunityBoard.portfolio_summary.volatility_index}</strong>
            </div>
            <div className="board-kpi">
              <span>Risk Exp.</span>
              <strong>{opportunityBoard.portfolio_summary.risk_exposure_pct}%</strong>
            </div>
          </div>

          <div className="board-sort-row">
            {(["score", "revenue", "risk"] as const).map((key) => (
              <button key={key} type="button" className={boardSort === key ? "compact-chip active" : "compact-chip"} onClick={() => setBoardSort(key)}>
                {key === "score" ? "Score" : key === "revenue" ? "Revenue" : "Risk"}
              </button>
            ))}
          </div>

          <ResponsiveContainer width="100%" height={Math.max(140, sortedBoardMatches.length * 36)} >
            <BarChart data={sortedBoardMatches} layout="vertical" margin={{ left: 10, right: 8 }}>
              <XAxis type="number" domain={[0, 100]} hide />
              <YAxis type="category" dataKey="title" width={110} stroke="#94a3b8" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ borderRadius: 14, border: "1px solid rgba(148,163,184,0.25)", background: "#fff", color: "#0f172a" }}
                formatter={(value, _name, props) => {
                  const p = (props as unknown as { payload: { recommendation_tag: string; revenue_estimate: number; peak_capacity_pct: number } }).payload;
                  return [`Score: ${value} | Rev: $${p.revenue_estimate.toLocaleString()} | Cap: ${p.peak_capacity_pct}%`, p.recommendation_tag];
                }}
              />
              <Bar dataKey="opportunity_score" radius={[0, 8, 8, 0]} maxBarSize={20}>
                {sortedBoardMatches.map((m) => (
                  <Cell key={m.match_id} fill={m.recommendation_tag === "top_opportunity" ? "#22C55E" : m.recommendation_tag === "solid" ? "#F97316" : "#94A3B8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <div className="board-legend">
            <span><i style={{ background: "#22C55E" }} />Top opportunity</span>
            <span><i style={{ background: "#F97316" }} />Solid</span>
            <span><i style={{ background: "#94A3B8" }} />Low priority</span>
          </div>
        </div>
      ) : null}

      {metricFilters.competition ? (
        <>
          <div className="chart-card">
            <h3>Your venue across this city's matches</h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={comparison?.comparisons ?? []} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="title" width={110} stroke="#94a3b8" tickLine={false} axisLine={false} />
                <Tooltip />
                <Bar dataKey="revenue_estimate" fill="#F97316" radius={[0, 8, 8, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <article className="chart-card">
            <h3>Nearby competition</h3>
            <div className="peer-list">
              {detail.peer_benchmark.map((peer) => (
                <div key={peer.business_id} className="peer-item">
                  <div>
                    <strong>{peer.name}</strong>
                    <small>
                      {titleCase(peer.type)} | {peer.google_rating.toFixed(1)} stars
                    </small>
                  </div>
                  <div className="peer-metrics">
                    <strong>{formatCompact(peer.served_visits_today)}</strong>
                    <small>Peak {peer.peak_label}</small>
                  </div>
                </div>
              ))}
            </div>
          </article>
        </>
      ) : null}

      {detail.playbook.watchouts.length ? (
        <div className="recommendation-card watchout-card">
          <p className="eyebrow">Operational watchouts</p>
          <div className="action-list">
            {detail.playbook.watchouts.map((watchout) => (
              <div key={watchout} className="action-item">
                <p>{watchout}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </aside>
  );
}
