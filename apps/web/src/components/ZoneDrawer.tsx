import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { MatchMeta, ZoneDetailResponse } from "../lib/types";
import { formatCompact, titleCase } from "../lib/format";

interface ZoneDrawerProps {
  detail: ZoneDetailResponse | null;
  match: MatchMeta;
  isLoading: boolean;
  onJumpToStep: (day: number, step: number) => void;
}

function ExplanationPanel({
  metricKey,
  detail,
}: {
  metricKey: string;
  detail: ZoneDetailResponse;
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

export function ZoneDrawer({ detail, match, isLoading, onJumpToStep }: ZoneDrawerProps) {
  if (!detail && !isLoading) {
    return (
      <aside className="panel drawer">
        <div className="section-header">
          <h2>Special venue intelligence</h2>
        </div>
        <p className="empty-state">Select the stadium or fan zone to inspect crowd waves, arrivals, and departures.</p>
      </aside>
    );
  }

  if (!detail || isLoading) {
    return (
      <aside className="panel drawer">
        <div className="section-header">
          <h2>Special venue intelligence</h2>
        </div>
        <div className="drawer-loading-shell">
          <div className="drawer-loading-bar" />
          <p>Loading live crowd-wave analytics for the selected venue.</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="panel drawer">
      <div className="section-header">
        <div>
          <h2>{detail.venue.name}</h2>
          <p className="drawer-subtitle">
            {titleCase(detail.entity_type)} | {match.title}
          </p>
        </div>
        <button type="button" className="compact-chip" onClick={() => onJumpToStep(detail.day, detail.peak.step)}>
          Jump to peak
        </button>
      </div>

      <div className="insight-grid">
        <article className="insight-card tone-accent">
          <div className="insight-card-top">
            <span>Active now</span>
            <ExplanationPanel metricKey="active_people" detail={detail} />
          </div>
          <strong>{formatCompact(detail.active_people_series_15m[detail.peak.step]?.value ?? detail.peak_active_people)}</strong>
          <small>{detail.peak.label} peak {formatCompact(detail.peak_active_people)}</small>
        </article>
        <article className="insight-card tone-warning">
          <div className="insight-card-top">
            <span>Cumulative entries</span>
            <ExplanationPanel metricKey="arrivals" detail={detail} />
          </div>
          <strong>{formatCompact(detail.cumulative_entries)}</strong>
          <small>Match-day arrivals</small>
        </article>
        <article className="insight-card tone-ok">
          <div className="insight-card-top">
            <span>Cumulative exits</span>
            <ExplanationPanel metricKey="departures" detail={detail} />
          </div>
          <strong>{formatCompact(detail.cumulative_exits)}</strong>
          <small>Match-day departures</small>
        </article>
        <article className="insight-card tone-accent">
          <span>Wave profile</span>
          <strong>{formatCompact(detail.wave_summary.in_match_peak)}</strong>
          <small>In-match peak occupancy</small>
        </article>
      </div>

      <div className="chart-card">
        <h3>Active people over time</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={detail.active_people_series_15m}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#203046" />
            <XAxis dataKey="label" stroke="#94a3b8" tickLine={false} axisLine={false} interval={7} />
            <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} />
            <Tooltip />
            <Area type="monotone" dataKey="value" stroke="#38BDF8" fill="rgba(56, 189, 248, 0.25)" strokeWidth={3} />
            {detail.active_people_series_15m
              .filter((point) => point.marker)
              .map((point) => (
                <ReferenceLine
                  key={`${point.step}-${point.marker}`}
                  x={point.label}
                  stroke={point.marker === "peak" ? "#F43F5E" : "#F97316"}
                  strokeDasharray="4 4"
                />
              ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h3>Arrivals and departures</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={detail.arrivals_series_15m.map((point, index) => ({
            label: point.label,
            arrivals: point.value,
            departures: detail.departures_series_15m[index]?.value ?? 0,
          }))}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#203046" />
            <XAxis dataKey="label" stroke="#94a3b8" tickLine={false} axisLine={false} interval={7} />
            <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} />
            <Tooltip />
            <Line type="monotone" dataKey="arrivals" stroke="#F97316" strokeWidth={2.5} dot={false} />
            <Line type="monotone" dataKey="departures" stroke="#38BDF8" strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="detail-grid">
        <article className="chart-card">
          <h3>Audience mix</h3>
          <div className="fan-mix-list">
            {Object.entries(detail.audience_mix).map(([segment, share]) => (
              <div key={segment} className="fan-mix-row">
                <span className="fan-mix-label">{titleCase(segment)}</span>
                <div className="fan-mix-bar-shell">
                  <div className="fan-mix-bar" style={{ width: `${share}%`, background: segment === "team_a" ? match.home_team.color : segment === "team_b" ? match.away_team.color : segment === "neutral" ? "#38BDF8" : "#94A3B8" }} />
                </div>
                <strong>{share}%</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="chart-card">
          <h3>Top inbound corridors</h3>
          <div className="peer-list">
            {detail.top_inbound_corridors.map((corridor) => (
              <div key={corridor.edge_id} className="peer-item">
                <div>
                  <strong>{corridor.road_name}</strong>
                  <small>Peak {corridor.peak_label}</small>
                </div>
                <div className="peer-metrics">
                  <strong>{formatCompact(corridor.peak_load)}</strong>
                </div>
              </div>
            ))}
          </div>
        </article>
      </div>

      <div className="chart-card">
        <h3>Wave summary</h3>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart
            data={[
              { label: "Pre-match", value: detail.wave_summary.pre_match_peak },
              { label: "In-match", value: detail.wave_summary.in_match_peak },
              { label: "Post-match", value: detail.wave_summary.post_match_peak },
            ]}
          >
            <XAxis dataKey="label" stroke="#94a3b8" tickLine={false} axisLine={false} />
            <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} hide />
            <Tooltip />
            <Bar dataKey="value" fill="#F97316" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </aside>
  );
}
