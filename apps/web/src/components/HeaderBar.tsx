import type { MatchMeta } from "../lib/types";
import { formatMatchDateTime } from "../lib/format";

interface HeaderBarProps {
  match: MatchMeta;
  timeLabel: string;
  scenarioId: string;
  onOpenProvenance: () => void;
  sourceAvailability: Record<string, boolean>;
}

export function HeaderBar({ match, timeLabel, scenarioId, onOpenProvenance, sourceAvailability }: HeaderBarProps) {
  const kickoffLabel = formatMatchDateTime(match.kickoff_local, { includeWeekday: true });
  const llmReady = sourceAvailability.gemini ?? sourceAvailability.llm_recommendations ?? sourceAvailability.anthropic ?? false;

  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">World Cup Venue Intelligence</p>
        <h1>{match.title}</h1>
        <p className="topbar-copy">
          {match.city} | {match.venue} | Kickoff {kickoffLabel}
        </p>
        <p className="topbar-copy">
          Track active visitors at businesses and active people at the stadium and fan zone. Click any venue marker to open its live operations view.
        </p>
      </div>
      <div className="topbar-actions">
        <div className="badge-strip">
          <span className="status-badge">Scenario: {scenarioId}</span>
          <span className="status-badge">Live time: {timeLabel}</span>
          <span className={`status-badge ${llmReady ? "live" : "seeded"}`}>
            {llmReady ? "Gemini Ready" : "Heuristic Insights"}
          </span>
          <span className={`status-badge ${sourceAvailability.google_places ? "live" : "seeded"}`}>
            {sourceAvailability.google_places ? "Places Ready" : "Seeded Ratings"}
          </span>
        </div>
        <button className="ghost-button" type="button" onClick={onOpenProvenance}>
          Data provenance
        </button>
      </div>
    </header>
  );
}
