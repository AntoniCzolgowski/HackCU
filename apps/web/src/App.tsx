import { startTransition, useDeferredValue, useEffect, useState } from "react";

import {
  createBusinessReport,
  fetchBusiness,
  fetchBusinessComparison,
  fetchMatches,
  fetchMeta,
  fetchOpportunityBoard,
  fetchProvenance,
  fetchReportJob,
  fetchSimulation,
  fetchZone,
} from "./lib/api";
import type {
  BusinessDetailResponse,
  BusinessMatchComparison,
  EntityType,
  LayerKey,
  MatchesResponse,
  MetaResponse,
  MetricFilterKey,
  OpportunityBoardResponse,
  ProvenanceResponse,
  ReportJobResponse,
  SimulationSnapshotResponse,
  ZoneDetailResponse,
} from "./lib/types";
import { HeaderBar } from "./components/HeaderBar";
import { ControlRail } from "./components/ControlRail";
import { BusinessDrawer } from "./components/BusinessDrawer";
import { ProvenancePanel } from "./components/ProvenancePanel";
import { MapScene } from "./components/MapScene";
import { MatchSelector } from "./components/MatchSelector";
import { ZoneDrawer } from "./components/ZoneDrawer";
import { CitySelector } from "./components/CitySelector";
import { formatMatchDateTime } from "./lib/format";

const INITIAL_DAY = 0;
const INITIAL_STEP = 36;
const INITIAL_CITY_ID = "dallas";
const PLAYBACK_SPEEDS = [1, 2, 4, 8] as const;
const DEFAULT_FILTERS: Record<MetricFilterKey, boolean> = {
  demand: true,
  capacity: true,
  revenue: true,
  audience: true,
  recommendations: true,
  competition: true,
  report_sections: true,
};

type PlaybackSpeed = (typeof PLAYBACK_SPEEDS)[number];
type SelectedEntity = { type: EntityType; id: string } | null;

export default function App() {
  const [bootNonce, setBootNonce] = useState(0);
  const [bootStartedAt, setBootStartedAt] = useState<number>(Date.now());
  const [bootProgress, setBootProgress] = useState(4);
  const [bootPhase, setBootPhase] = useState("Loading match schedule");
  const [bootElapsedMs, setBootElapsedMs] = useState(0);
  const [matchesData, setMatchesData] = useState<MatchesResponse | null>(null);
  const [selectedCityId, setSelectedCityId] = useState(INITIAL_CITY_ID);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [snapshot, setSnapshot] = useState<SimulationSnapshotResponse | null>(null);
  const [businessDetail, setBusinessDetail] = useState<BusinessDetailResponse | null>(null);
  const [zoneDetail, setZoneDetail] = useState<ZoneDetailResponse | null>(null);
  const [businessComparison, setBusinessComparison] = useState<BusinessMatchComparison | null>(null);
  const [opportunityBoard, setOpportunityBoard] = useState<OpportunityBoardResponse | null>(null);
  const [provenance, setProvenance] = useState<ProvenanceResponse | null>(null);
  const [selectedDay, setSelectedDay] = useState(INITIAL_DAY);
  const [selectedStep, setSelectedStep] = useState(INITIAL_STEP);
  const [selectedLayer, setSelectedLayer] = useState<LayerKey>("total");
  const [selectedScenario] = useState("baseline");
  const [selectedEntity, setSelectedEntity] = useState<SelectedEntity>(null);
  const [entityLoading, setEntityLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<PlaybackSpeed>(1);
  const [showProvenance, setShowProvenance] = useState(false);
  const [metricFilters, setMetricFilters] = useState(DEFAULT_FILTERS);
  const [reportState, setReportState] = useState<{ isGenerating: boolean; status: string | null; job: ReportJobResponse | null }>({
    isGenerating: false,
    status: null,
    job: null,
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    setMatchesData(null);
    setSelectedMatchId(null);
    setMeta(null);
    setSnapshot(null);
    setBusinessDetail(null);
    setZoneDetail(null);
    setBusinessComparison(null);
    setOpportunityBoard(null);
    setSelectedEntity(null);
    setBootStartedAt(Date.now());
    setBootElapsedMs(0);
    setBootProgress(12);
    setBootPhase("Loading match schedule");
    fetchMatches(selectedCityId)
      .then((payload) => {
        setMatchesData(payload);
        setSelectedMatchId(payload.default_match_id);
        setBootProgress(34);
        setBootPhase("Loading match metadata");
      })
      .catch((reason: Error) => {
        setBootPhase("Boot failed");
        setError(reason.message);
      });
  }, [bootNonce, selectedCityId]);

  const selectedCityMeta = matchesData?.available_cities.find((city) => city.city_id === selectedCityId) ?? null;
  const selectedCityReady = selectedCityMeta?.simulation_ready ?? true;
  const selectedMatchSummary = matchesData?.matches.find((match) => match.match_id === selectedMatchId) ?? null;

  useEffect(() => {
    if (!selectedMatchId) return;
    if (!selectedCityReady) {
      setMeta(null);
      setSnapshot(null);
      setBusinessDetail(null);
      setZoneDetail(null);
      setBusinessComparison(null);
      setBootProgress(100);
      setBootPhase("Schedule preview");
      return;
    }
    setError(null);
    setMeta(null);
    setSnapshot(null);
    setBusinessDetail(null);
    setZoneDetail(null);
    setBusinessComparison(null);
    setSelectedEntity(null);
    setSelectedDay(INITIAL_DAY);
    setSelectedStep(INITIAL_STEP);
    setMetricFilters(DEFAULT_FILTERS);
    setBootProgress(52);
    setBootPhase("Loading city graph and venue metadata");
    fetchMeta({ cityId: selectedCityId, matchId: selectedMatchId })
      .then((payload) => {
        startTransition(() => setMeta(payload));
        setBootProgress(72);
        setBootPhase("Preparing first simulation snapshot");
      })
      .catch((reason: Error) => {
        setBootPhase("Boot failed");
        setError(reason.message);
      });
  }, [selectedCityId, selectedCityReady, selectedMatchId]);

  useEffect(() => {
    if (!meta || !selectedMatchId || !selectedCityReady) return;
    let cancelled = false;
    setBootProgress((value) => (value < 84 ? 84 : value));
    setBootPhase("Loading first match-day snapshot");
    fetchSimulation({
      day: selectedDay,
      step: selectedStep,
      scenario: selectedScenario,
      layer: selectedLayer,
      cityId: selectedCityId,
      matchId: selectedMatchId,
    })
      .then((payload) => {
        if (cancelled) return;
        startTransition(() => setSnapshot(payload));
        setBootProgress(100);
        setBootPhase("Ready");
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setBootPhase("Boot failed");
          setError(reason.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [meta, selectedDay, selectedLayer, selectedMatchId, selectedScenario, selectedStep, selectedCityId, selectedCityReady]);

  useEffect(() => {
    if (!snapshot?.business_overlay.length) return;
    if (selectedEntity) return;
    setSelectedEntity({ type: "business", id: snapshot.business_overlay[0].business_id });
  }, [selectedEntity, snapshot]);

  useEffect(() => {
    if (!selectedEntity || !selectedMatchId || !selectedCityReady) {
      setBusinessDetail(null);
      setZoneDetail(null);
      setBusinessComparison(null);
      return;
    }

    let cancelled = false;
    setEntityLoading(true);
    setReportState({ isGenerating: false, status: null, job: null });

    if (selectedEntity.type === "business") {
      fetchBusiness({
        businessId: selectedEntity.id,
        day: selectedDay,
        scenario: selectedScenario,
        cityId: selectedCityId,
        matchId: selectedMatchId,
      })
        .then((payload) => {
          if (!cancelled) {
            startTransition(() => {
              setBusinessDetail(payload);
              setZoneDetail(null);
            });
          }
        })
        .catch((reason: Error) => {
          if (!cancelled) setError(reason.message);
        })
        .finally(() => {
          if (!cancelled) setEntityLoading(false);
        });

      fetchBusinessComparison({ businessId: selectedEntity.id, cityId: selectedCityId })
        .then((payload) => {
          if (!cancelled) startTransition(() => setBusinessComparison(payload));
        })
        .catch(() => {
          if (!cancelled) setBusinessComparison(null);
        });

      fetchOpportunityBoard({ businessId: selectedEntity.id, cityId: selectedCityId })
        .then((payload) => {
          if (!cancelled) startTransition(() => setOpportunityBoard(payload));
        })
        .catch(() => {
          if (!cancelled) setOpportunityBoard(null);
        });
    } else {
      fetchZone({
        zoneId: selectedEntity.id,
        day: selectedDay,
        scenario: selectedScenario,
        cityId: selectedCityId,
        matchId: selectedMatchId,
      })
        .then((payload) => {
          if (!cancelled) {
            startTransition(() => {
              setZoneDetail(payload);
              setBusinessDetail(null);
              setBusinessComparison(null);
            });
          }
        })
        .catch((reason: Error) => {
          if (!cancelled) setError(reason.message);
        })
        .finally(() => {
          if (!cancelled) setEntityLoading(false);
        });
    }

    return () => {
      cancelled = true;
    };
  }, [selectedCityId, selectedCityReady, selectedDay, selectedEntity, selectedMatchId, selectedScenario]);

  useEffect(() => {
    if (!isPlaying || !meta) return;
    const handle = window.setInterval(() => {
      setSelectedStep((previousStep) => {
        if (previousStep < meta.timeline.steps_per_day - 1) return previousStep + 1;
        setSelectedDay((previousDay) => {
          const index = meta.timeline.days.indexOf(previousDay);
          return meta.timeline.days[(index + 1) % meta.timeline.days.length];
        });
        return 0;
      });
    }, Math.max(120, Math.round(950 / playbackSpeed)));
    return () => {
      window.clearInterval(handle);
    };
  }, [isPlaying, meta, playbackSpeed]);

  const deferredSnapshot = useDeferredValue(snapshot);
  const isBooting = !matchesData || (selectedCityReady && (!meta || !deferredSnapshot));

  useEffect(() => {
    if (!isBooting) {
      setBootElapsedMs(Date.now() - bootStartedAt);
      return;
    }
    const handle = window.setInterval(() => {
      setBootElapsedMs(Date.now() - bootStartedAt);
    }, 120);
    return () => {
      window.clearInterval(handle);
    };
  }, [bootStartedAt, isBooting]);

  const handleOpenProvenance = async () => {
    setShowProvenance(true);
    if (!provenance) {
      try {
        setProvenance(await fetchProvenance());
      } catch (reason) {
        setError((reason as Error).message);
      }
    }
  };

  const handleJumpToStep = (day: number, step: number) => {
    setIsPlaying(false);
    setSelectedDay(day);
    setSelectedStep(step);
  };

  const handleJumpToWave = () => {
    if (!meta) return;
    setSelectedDay(0);
    setSelectedStep(meta.timeline.match_markers.final_whistle_step);
    setIsPlaying(true);
    setPlaybackSpeed(2);
  };

  const handleToggleMetricFilter = (key: MetricFilterKey) => {
    setMetricFilters((current) => ({ ...current, [key]: !current[key] }));
  };

  const handleGenerateReport = async () => {
    if (!selectedEntity || selectedEntity.type !== "business" || !selectedMatchId) return;
    setReportState({ isGenerating: true, status: "queued", job: null });
    try {
      const created = await createBusinessReport({
        businessId: selectedEntity.id,
        day: selectedDay,
        scenario: selectedScenario,
        visibleSections: metricFilters,
        cityId: selectedCityId,
        matchId: selectedMatchId,
      });
      setReportState({ isGenerating: true, status: created.status, job: created });
    } catch (reason) {
      setReportState({ isGenerating: false, status: "failed", job: null });
      setError((reason as Error).message);
    }
  };

  useEffect(() => {
    if (!reportState.isGenerating || !reportState.job?.job_id) return;
    const handle = window.setInterval(async () => {
      try {
        const job = await fetchReportJob(reportState.job!.job_id);
        if (job.status === "completed" && job.download_url) {
          window.clearInterval(handle);
          setReportState({ isGenerating: false, status: "completed", job });
          window.open(job.download_url, "_blank", "noopener,noreferrer");
        } else if (job.status === "failed") {
          window.clearInterval(handle);
          setReportState({ isGenerating: false, status: "failed", job });
        } else {
          setReportState({ isGenerating: true, status: job.status, job });
        }
      } catch (reason) {
        window.clearInterval(handle);
        setReportState({ isGenerating: false, status: "failed", job: null });
        setError((reason as Error).message);
      }
    }, 900);
    return () => window.clearInterval(handle);
  }, [reportState]);

  const rightPanel = !meta ? null : !selectedEntity || selectedEntity.type === "business" || businessDetail ? (
    <BusinessDrawer
      detail={businessDetail}
      comparison={businessComparison}
      opportunityBoard={opportunityBoard}
      match={meta.match}
      isLoading={entityLoading}
      metricFilters={metricFilters}
      onToggleMetricFilter={handleToggleMetricFilter}
      onJumpToStep={handleJumpToStep}
      onGenerateReport={handleGenerateReport}
      reportState={{ isGenerating: reportState.isGenerating, status: reportState.status }}
    />
  ) : (
    <ZoneDrawer detail={zoneDetail} match={meta.match} isLoading={entityLoading} onJumpToStep={handleJumpToStep} />
  );

  if (isBooting) {
    return (
      <main className="app-shell loading-shell">
        <div className="loading-card">
          <p className="eyebrow">MatchFlow World Cup</p>
          <h1>Booting simulation layers</h1>
          <p>Loading seeded city graph, special-venue dashboards, and the first match-day snapshot.</p>
          <div className="loading-progress-shell" aria-label="Application loading progress">
            <div className="loading-progress-bar" style={{ width: `${bootProgress}%` }} />
          </div>
          <div className="loading-progress-meta">
            <strong>{bootProgress}%</strong>
            <span>{bootPhase}</span>
            <small>{(bootElapsedMs / 1000).toFixed(1)}s elapsed</small>
          </div>
          {error ? <div className="loading-error">{error}</div> : null}
          <div className="chip-row">
            <button className="ghost-button" type="button" onClick={() => setBootNonce((value) => value + 1)}>
              Retry boot
            </button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <HeaderBar
        match={(meta?.match ?? {
          ...selectedMatchSummary!,
          city_id: selectedCityId,
          city: selectedCityMeta?.label ?? selectedCityId,
          day_offsets: [-1, 0, 1],
          step_minutes: 15,
          timeline: { start_hour: 6, end_hour: 26, steps: 80 },
        }) as MetaResponse["match"]}
        timeLabel={deferredSnapshot?.time_label ?? "Schedule preview"}
        scenarioId={selectedScenario}
        sourceAvailability={meta?.source_availability ?? { google_places: false, anthropic: false, baseline_seed: true }}
        onOpenProvenance={handleOpenProvenance}
      />

      <CitySelector cities={matchesData.available_cities} selectedCityId={selectedCityId} onSelectCity={setSelectedCityId} />
      <MatchSelector matches={matchesData.matches} selectedMatchId={selectedMatchId!} onSelectMatch={setSelectedMatchId} />

      {error ? <div className="error-banner">{error}</div> : null}

      {!selectedCityReady ? (
        <section className="panel schedule-preview-panel">
          <div className="section-header">
            <div>
              <h2>{selectedCityMeta?.label ?? selectedCityId}</h2>
              <p className="drawer-subtitle">Schedule preview mode. This city is in the schedule registry, but the live map pack is not generated yet.</p>
            </div>
          </div>
          <div className="schedule-preview-grid">
            {matchesData.matches.map((match) => (
              <article key={match.match_id} className="chart-card">
                <p className="eyebrow">{match.stage}</p>
                <strong>{match.title}</strong>
                <p>{formatMatchDateTime(match.kickoff_local)}</p>
                <small>{match.venue}</small>
              </article>
            ))}
          </div>
        </section>
      ) : (
        <div className="layout-grid">
          <ControlRail
            meta={meta!}
            snapshot={deferredSnapshot!}
            selectedDay={selectedDay}
            selectedStep={selectedStep}
            selectedLayer={selectedLayer}
            isPlaying={isPlaying}
            playbackSpeed={playbackSpeed}
            playbackSpeeds={PLAYBACK_SPEEDS}
            selectedEntity={selectedEntity}
            onSelectDay={setSelectedDay}
            onSelectStep={setSelectedStep}
            onSelectLayer={setSelectedLayer}
            onSelectPlaybackSpeed={(speed) => setPlaybackSpeed(speed)}
            onTogglePlay={() => setIsPlaying((value) => !value)}
            onSelectEntity={(type, id) => setSelectedEntity({ type, id })}
            onJumpToWave={handleJumpToWave}
          />

          <MapScene
            meta={meta!}
            snapshot={deferredSnapshot!}
            selectedEntity={selectedEntity}
            onSelectEntity={(type, id) => setSelectedEntity({ type, id })}
          />

          <div className="right-column">{rightPanel}</div>
        </div>
      )}

      <ProvenancePanel provenance={showProvenance ? provenance : null} onClose={() => setShowProvenance(false)} />
    </main>
  );
}
