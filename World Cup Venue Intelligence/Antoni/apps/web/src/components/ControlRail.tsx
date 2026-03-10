import type { EntityType, LayerKey, MetaResponse, SimulationSnapshotResponse } from "../lib/types";
import { formatCompact, formatPercent, titleCase } from "../lib/format";

interface ControlRailProps {
  meta: MetaResponse;
  snapshot: SimulationSnapshotResponse;
  selectedDay: number;
  selectedStep: number;
  selectedLayer: LayerKey;
  isPlaying: boolean;
  playbackSpeed: 1 | 2 | 4 | 8;
  playbackSpeeds: readonly (1 | 2 | 4 | 8)[];
  selectedEntity: { type: EntityType; id: string } | null;
  onSelectDay: (day: number) => void;
  onSelectStep: (step: number) => void;
  onSelectLayer: (layer: LayerKey) => void;
  onSelectPlaybackSpeed: (speed: 1 | 2 | 4 | 8) => void;
  onTogglePlay: () => void;
  onSelectEntity: (type: EntityType, id: string) => void;
  onJumpToWave: () => void;
}

export function ControlRail({
  meta,
  snapshot,
  selectedDay,
  selectedStep,
  selectedLayer,
  isPlaying,
  playbackSpeed,
  playbackSpeeds,
  selectedEntity,
  onSelectDay,
  onSelectStep,
  onSelectLayer,
  onSelectPlaybackSpeed,
  onTogglePlay,
  onSelectEntity,
  onJumpToWave,
}: ControlRailProps) {
  const zoneNameById = new Map(meta.zones.map((zone) => [zone.id, zone.name]));
  const visibleBusinesses = snapshot.business_overlay.filter((business) => business.type !== "hotel").slice(0, 14);

  return (
    <aside className="panel control-rail">
      <section className="panel-section">
        <div className="section-header">
          <h2>Playback</h2>
          <button className="primary-button" type="button" onClick={onTogglePlay}>
            {isPlaying ? "Pause" : "Play"}
          </button>
        </div>
        <div className="chip-row">
          {meta.timeline.days.map((day) => (
            <button
              key={day}
              className={day === selectedDay ? "chip active" : "chip"}
              type="button"
              onClick={() => onSelectDay(day)}
            >
              {day === 0 ? "Match Day" : day < 0 ? "Day -1" : "Day +1"}
            </button>
          ))}
        </div>
        <label className="slider-label" htmlFor="timeline">
          Step {selectedStep + 1} | {snapshot.time_label}
        </label>
        <input
          id="timeline"
          className="timeline-slider"
          type="range"
          min={0}
          max={meta.timeline.steps_per_day - 1}
          value={selectedStep}
          onChange={(event) => onSelectStep(Number(event.target.value))}
        />
        <div className="timeline-endpoints">
          <span>{meta.timeline.time_labels[0]}</span>
          {selectedDay === 0 ? <span className="timeline-kickoff-pill">Kickoff {meta.timeline.match_markers.kickoff_label}</span> : null}
          <span>{meta.timeline.time_labels[meta.timeline.time_labels.length - 1]}</span>
        </div>
        <div className="section-header compact">
          <h3>Speed</h3>
          <span className="stat-footnote">Playback only</span>
        </div>
        <div className="chip-row">
          {playbackSpeeds.map((speed) => (
            <button
              key={speed}
              className={speed === playbackSpeed ? "chip active" : "chip"}
              type="button"
              onClick={() => onSelectPlaybackSpeed(speed)}
            >
              {speed}x
            </button>
          ))}
        </div>
        <button className="wave-button" type="button" onClick={onJumpToWave}>
          Jump to Post-Match Wave
        </button>
      </section>

      <section className="panel-section">
        <div className="section-header">
          <h2>What to watch now</h2>
          <span className="stat-footnote">Live cues</span>
        </div>
        <div className="story-stack">
          {snapshot.summary.watch_items.map((item) => (
            <article key={item.label} className="story-card">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <small>{item.detail}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel-section">
        <div className="section-header">
          <h2>Audience layer</h2>
          <span className="stat-footnote">{titleCase(selectedLayer)}</span>
        </div>
        <div className="chip-grid">
          {meta.available_layers.map((layer) => (
            <button
              key={layer}
              className={layer === selectedLayer ? "chip active" : "chip"}
              type="button"
              onClick={() => onSelectLayer(layer)}
            >
              {titleCase(layer)}
            </button>
          ))}
        </div>
        <div className="kpi-stack compact-kpi-stack">
          <article className="kpi-card">
            <span>Visible crowd</span>
            <strong>{formatCompact(snapshot.summary.city_total)}</strong>
          </article>
          <article className="kpi-card">
            <span>In motion</span>
            <strong>{formatCompact(snapshot.summary.active_travelers)}</strong>
          </article>
        </div>
      </section>

      <section className="panel-section">
        <div className="section-header">
          <h2>Special venues</h2>
          <span className="stat-footnote">Stadium and fan zone</span>
        </div>
        <div className="venue-list">
          {snapshot.special_overlay.map((venue) => (
            <button
              key={venue.entity_id}
              type="button"
              className={selectedEntity?.id === venue.entity_id ? "venue-item active" : "venue-item"}
              onClick={() => onSelectEntity(venue.entity_type, venue.entity_id)}
            >
              <div className="venue-meta">
                <span>{venue.name}</span>
                <small>{titleCase(venue.entity_type)} | {formatPercent(venue.crowd_pressure)}</small>
              </div>
              <strong>{formatCompact(venue.value)}</strong>
            </button>
          ))}
        </div>
      </section>

      <section className="panel-section">
        <div className="section-header">
          <h2>Venue watchlist</h2>
          <span className="stat-footnote">{visibleBusinesses.length} frontline venues</span>
        </div>
        <div className="venue-list">
          {visibleBusinesses.map((business) => (
            <button
              key={business.business_id}
              type="button"
              className={selectedEntity?.id === business.business_id ? "venue-item active" : "venue-item"}
              onClick={() => onSelectEntity("business", business.business_id)}
            >
              <div className="venue-meta">
                <span>{business.name}</span>
                <small>
                  {titleCase(business.type)} | {zoneNameById.get(business.zone_id) ?? business.zone_id} | {business.google_rating.toFixed(1)} stars
                </small>
              </div>
              <strong>{formatCompact(business.value)}</strong>
            </button>
          ))}
        </div>
      </section>
    </aside>
  );
}
