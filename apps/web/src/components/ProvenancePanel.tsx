import type { ProvenanceResponse } from "../lib/types";

interface ProvenancePanelProps {
  provenance: ProvenanceResponse | null;
  onClose: () => void;
}

export function ProvenancePanel({ provenance, onClose }: ProvenancePanelProps) {
  if (!provenance) {
    return null;
  }

  return (
    <div className="provenance-overlay">
      <div className="panel provenance-panel">
        <div className="section-header">
          <div>
            <h2>Data provenance</h2>
            <p className="drawer-subtitle">Clear labeling for real, seeded, and simulated layers.</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="provenance-list">
          {provenance.sources.map((source) => (
            <article key={source.id} className="provenance-item">
              <strong>{source.label}</strong>
              <span>{source.status}</span>
              <p>{source.details}</p>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
