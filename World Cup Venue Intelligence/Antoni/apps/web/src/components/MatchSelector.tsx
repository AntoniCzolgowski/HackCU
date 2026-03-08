import type { MatchSummary } from "../lib/types";
import { formatMatchDate, formatMatchTime } from "../lib/format";

interface MatchSelectorProps {
  matches: MatchSummary[];
  selectedMatchId: string;
  onSelectMatch: (matchId: string) => void;
}

export function MatchSelector({ matches, selectedMatchId, onSelectMatch }: MatchSelectorProps) {
  return (
    <nav className="match-selector-row">
      {matches.map((match) => {
        const dateLabel = formatMatchDate(match.kickoff_local);
        const timeLabel = formatMatchTime(match.kickoff_local);
        const active = match.match_id === selectedMatchId;

        return (
          <button
            key={match.match_id}
            type="button"
            className={active ? "match-card active" : "match-card"}
            style={{ borderTopColor: active ? match.home_team.color : undefined }}
            onClick={() => onSelectMatch(match.match_id)}
          >
            <span className="match-card-teams">
              <span className="team-dot" style={{ background: match.home_team.color }} />
              {match.home_team.name}
              <span className="match-vs">vs</span>
              <span className="team-dot" style={{ background: match.away_team.color }} />
              {match.away_team.name}
            </span>
            <span className="match-card-meta">
              <span className="match-stage-badge">{match.stage}</span>
              <span>{dateLabel}</span>
              <span>{timeLabel}</span>
            </span>
            <span className="match-card-venue">{match.venue}</span>
          </button>
        );
      })}
    </nav>
  );
}
