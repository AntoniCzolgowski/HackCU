import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("./components/MapScene", () => ({
  MapScene: ({ onSelectEntity }: { onSelectEntity: (type: "business" | "stadium" | "fanzone", id: string) => void }) => (
    <div>
      <button type="button" onClick={() => onSelectEntity("business", "biz_texas_live")}>
        Select business
      </button>
      <button type="button" onClick={() => onSelectEntity("stadium", "stadium_zone")}>
        Select stadium
      </button>
    </div>
  ),
}));

vi.mock("./lib/api", () => ({
  fetchMatches: vi.fn(async (cityId?: string) => {
    if (cityId === "monterrey") {
      return {
        city_id: "monterrey",
        available_cities: [
          { city_id: "dallas", label: "Dallas-Arlington", simulation_ready: true },
          { city_id: "monterrey", label: "Monterrey", simulation_ready: false },
        ],
        default_match_id: "monterrey-uefa-winner-b-tunisia-2026-06-14",
        matches: [
          {
            match_id: "monterrey-uefa-winner-b-tunisia-2026-06-14",
            title: "Poland vs Tunisia",
            stage: "Group Stage",
            kickoff_local: "2026-06-14T20:00:00-06:00",
            venue: "Estadio BBVA",
            venue_capacity: 53000,
            home_team: { id: "poland", name: "Poland", color: "#DC143C" },
            away_team: { id: "tunisia", name: "Tunisia", color: "#E70013" },
          },
        ],
      };
    }

    return {
      city_id: "dallas",
      available_cities: [
        { city_id: "dallas", label: "Dallas-Arlington", simulation_ready: true },
        { city_id: "monterrey", label: "Monterrey", simulation_ready: false },
      ],
      default_match_id: "dallas-netherlands-japan-2026-06-14",
      matches: [
        {
          match_id: "dallas-netherlands-japan-2026-06-14",
          title: "Netherlands vs Japan",
          stage: "Group Stage",
          kickoff_local: "2026-06-14T18:00:00-05:00",
          venue: "AT&T Stadium",
          venue_capacity: 80000,
          home_team: { id: "netherlands", name: "Netherlands", color: "#F97316" },
          away_team: { id: "japan", name: "Japan", color: "#BC002D" },
        },
      ],
    };
  }),
  fetchMeta: vi.fn().mockResolvedValue({
    app: { name: "MatchFlow World Cup Intelligence", scenario_ids: ["baseline"], city_id: "dallas" },
    match: {
      match_id: "dallas-netherlands-japan-2026-06-14",
      title: "Netherlands vs Japan",
      stage: "Group Stage",
      city_id: "dallas",
      city: "Dallas-Arlington",
      venue: "AT&T Stadium",
      venue_capacity: 80000,
      kickoff_local: "2026-06-14T18:00:00-05:00",
      home_team: { id: "netherlands", name: "Netherlands", color: "#F97316" },
      away_team: { id: "japan", name: "Japan", color: "#BC002D" },
      day_offsets: [-1, 0, 1],
      step_minutes: 15,
      timeline: { start_hour: 6, end_hour: 26, steps: 80 },
    },
    timeline: {
      step_minutes: 15,
      steps_per_day: 80,
      time_labels: Array.from({ length: 80 }, (_, index) => `${String((index + 6) % 24).padStart(2, "0")}:00`),
      days: [-1, 0, 1],
      match_markers: {
        kickoff_step: 48,
        halftime_step: 52,
        final_whistle_step: 56,
        kickoff_label: "18:00",
        halftime_label: "19:00",
        final_whistle_label: "20:45",
      },
    },
    zones: [
      {
        id: "texas_live_zone",
        name: "Entertainment District",
        kind: "bar_cluster",
        node_id: "texas_live",
        center: [-97.0839, 32.7479],
        radius_m: 600,
        focus_color: "#F43F5E",
        capacity: 9000,
        node: { id: "texas_live", label: "Texas Live!", lat: 32.7479, lng: -97.0839 },
      },
    ],
    edges: [
      {
        id: "downtown_stadium",
        source: "downtown_dallas",
        target: "stadium",
        road_name: "I-30 Mainline",
        capacity: 9600,
        base_travel_minutes: 28,
        distance_km: 29.8,
        kind: "highway",
        bidirectional: true,
        path: [[-96.8, 32.77], [-96.9, 32.76], [-97.09, 32.74]],
      },
    ],
    businesses: [
      {
        id: "biz_texas_live",
        name: "Texas Live!",
        type: "sports_bar",
        zone_id: "texas_live_zone",
        node_id: "texas_live",
        lat: 32.7479,
        lng: -97.0839,
        rating: 4.6,
        price_level: 2,
        capacity_estimate: 4200,
        hours: "10:00-02:00",
        source: "seeded_real",
        signature_item: "watch-party packages",
      },
    ],
    special_venues: [
      { id: "stadium_zone", name: "AT&T Stadium", entity_type: "stadium", zone_id: "stadium_zone", lat: 32.7473, lng: -97.0945, comfort_capacity: 80000, kind: "stadium" },
      { id: "fanzone_zone", name: "FIFA Fan Zone", entity_type: "fanzone", zone_id: "fanzone_zone", lat: 32.7574, lng: -97.0715, comfort_capacity: 18000, kind: "fanzone" },
    ],
    pois: [],
    weather: { "0": { temp_c: 35, condition: "Hot afternoon", walking_modifier: 0.82 } },
    map_config: {
      provider: "google_maps_js",
      google_maps_api_key: "test-key",
      default_map_type: "roadmap",
      available_map_types: ["roadmap", "terrain", "hybrid"],
      initial_center: [-96.98, 32.78],
      initial_zoom: 9.5,
    },
    available_layers: ["total", "team_a", "team_b", "neutral", "locals"],
    source_availability: { google_places: false, anthropic: false, baseline_seed: true },
  }),
  fetchSimulation: vi.fn().mockResolvedValue({
    scenario_id: "baseline",
    day: 0,
    step: 36,
    time_label: "15:00",
    layer: "total",
    zones: [
      { zone_id: "texas_live_zone", name: "Entertainment District", kind: "bar_cluster", center: [-97.0839, 32.7479], value: 12000, capacity: 9000, utilization: 1.33, focus_color: "#F43F5E" },
    ],
    edges: [
      { edge_id: "downtown_stadium", road_name: "I-30 Mainline", kind: "highway", load: 6400, capacity: 9600, congestion: 0.66 },
    ],
    business_overlay: [
      { business_id: "biz_texas_live", name: "Texas Live!", type: "sports_bar", zone_id: "texas_live_zone", value: 3400, rating: 4.6, google_rating: 4.6, capacity_estimate: 4200 },
    ],
    special_overlay: [
      { entity_id: "stadium_zone", entity_type: "stadium", zone_id: "stadium_zone", name: "AT&T Stadium", value: 52000, comfort_capacity: 80000, crowd_pressure: 0.65, lat: 32.7473, lng: -97.0945 },
      { entity_id: "fanzone_zone", entity_type: "fanzone", zone_id: "fanzone_zone", name: "FIFA Fan Zone", value: 14000, comfort_capacity: 18000, crowd_pressure: 0.78, lat: 32.7574, lng: -97.0715 },
    ],
    summary: {
      city_total: 52000,
      active_travelers: 8000,
      busiest_zone: { zone_id: "texas_live_zone", name: "Entertainment District", kind: "bar_cluster", center: [-97.0839, 32.7479], value: 12000, capacity: 9000, utilization: 1.33, focus_color: "#F43F5E" },
      busiest_business: { business_id: "biz_texas_live", name: "Texas Live!", type: "sports_bar", zone_id: "texas_live_zone", value: 3400, rating: 4.6, google_rating: 4.6, capacity_estimate: 4200 },
      busiest_special_venue: { entity_id: "stadium_zone", entity_type: "stadium", zone_id: "stadium_zone", name: "AT&T Stadium", value: 52000, comfort_capacity: 80000, crowd_pressure: 0.65, lat: 32.7473, lng: -97.0945 },
      most_congested_edge: { edge_id: "downtown_stadium", road_name: "I-30 Mainline", kind: "highway", load: 6400, capacity: 9600, congestion: 0.66 },
      weather: { temp_c: 35, condition: "Hot afternoon", walking_modifier: 0.82 },
      watch_items: [
        { label: "Top live district", value: "Entertainment District", detail: "133% district utilization" },
        { label: "Business to watch", value: "Texas Live!", detail: "3400 active visitors now" },
        { label: "Special venue wave", value: "AT&T Stadium", detail: "52000 active people now" },
      ],
    },
  }),
  fetchBusiness: vi.fn().mockResolvedValue({
    entity_type: "business",
    business: {
      id: "biz_texas_live",
      name: "Texas Live!",
      type: "sports_bar",
      zone_id: "texas_live_zone",
      node_id: "texas_live",
      lat: 32.7479,
      lng: -97.0839,
      rating: 4.6,
      price_level: 2,
      capacity_estimate: 4200,
      hours: "10:00-02:00",
      source: "seeded_real",
      signature_item: "watch-party packages",
    },
    day: 0,
    scenario_id: "baseline",
    active_visitors_series_15m: [
      { step: 48, label: "18:00", value: 600, marker: "kickoff" },
      { step: 50, label: "18:30", value: 900, marker: "peak" },
    ],
    peak: { step: 50, label: "18:30", active_visitors: 900 },
    peak_active_visitors: 900,
    peak_capacity_pct_capped: 120,
    served_visits_today: 340,
    served_revenue: { total: 12400, avg_spend: 36, service_capture_rate: 0.92, served_visits_today: 340 },
    google_rating: { value: 4.6, source: "seeded_real" },
    nationality_mix: { team_a: 20, team_b: 60, neutral: 10, locals: 10 },
    day_comparison: [
      { day: -1, label: "Day Before", served_visits_today: 90, peak_active_visitors: 60, peak_label: "18:00" },
      { day: 0, label: "Match Day", served_visits_today: 340, peak_active_visitors: 900, peak_label: "18:30" },
      { day: 1, label: "Day After", served_visits_today: 120, peak_active_visitors: 80, peak_label: "11:00" },
    ],
    zone_context: { zone_id: "texas_live_zone", zone_name: "Entertainment District", zone_kind: "bar_cluster", venues_in_zone: 4, venue_rank: 1, zone_total_served_visits: 920, share_of_zone_demand: 37 },
    audience_profile: { dominant_segment: "team_b", dominant_label: "Japan", dominant_share: 60, spend_profile: "high-volume watch-party spend" },
    playbook: {
      pressure_level: "High",
      tone: "warning",
      peak_window: "18:00-19:00",
      estimated_turns: 4.8,
      dominant_segment: "team_b",
      dominant_label: "Japan",
      dominant_share: 60,
      spend_profile: "high-volume watch-party spend",
      action_options: [
        { title: "Staffing", detail: "Stage one dedicated queue manager.", priority: "urgent", timing: "24h before" },
      ],
      watchouts: ["Demand is projected beyond practical comfort capacity."],
    },
    peer_benchmark: [{ business_id: "peer-1", name: "The Tipsy Oak", type: "sports_bar", served_visits_today: 210, peak_label: "18:15", google_rating: 4.3 }],
    insight_cards: [
      { label: "Pressure", value: "High", detail: "Peak window 18:00-19:00", tone: "warning", metric_key: "pressure" },
      { label: "Est. Revenue", value: "$12,400", detail: "340 served visits x $36 avg", tone: "accent", metric_key: "served_revenue" },
    ],
    metric_explanations: {
      pressure: { title: "Pressure", definition: "Stress level", formula: "pressure = label(peak_capacity_pct_capped)", inputs: { peak_capacity_pct_capped: 120 }, notes: [] },
      served_revenue: { title: "Revenue", definition: "Revenue logic", formula: "served_visits_today x weighted_avg_spend x service_capture_rate", inputs: { served_visits_today: 340 }, notes: [] },
      peak_capacity: { title: "Peak", definition: "Peak capacity", formula: "min(150, peak_active_visitors / capacity_estimate x 100)", inputs: { peak_active_visitors: 900 }, notes: [] },
      zone_share: { title: "Zone share", definition: "Share", formula: "served_visits / zone total", inputs: { served_visits_today: 340 }, notes: [] },
      active_visitors: { title: "Active visitors", definition: "Canonical series", formula: "active_visitors_15m[t]", inputs: { peak_active_visitors: 900 }, notes: [] },
    },
    recommendation: { source: "heuristic", text: "Stage one dedicated queue manager and simplify service at kickoff.", model: null },
    visible_sections: { demand: true, capacity: true, revenue: true, audience: true, recommendations: true, competition: true, report_sections: true },
    provenance: { business_source: "seeded_real", forecast_source: "simulated_active_visitors", recommendation_source: "heuristic" },
    report_support: { can_generate_pdf: true },
  }),
  fetchBusinessComparison: vi.fn().mockResolvedValue({
    business_id: "biz_texas_live",
    city_id: "dallas",
    comparisons: [
      {
        match_id: "dallas-netherlands-japan-2026-06-14",
        title: "Netherlands vs Japan",
        stage: "Group Stage",
        kickoff_local: "2026-06-14T18:00:00-05:00",
        home_team: { id: "netherlands", name: "Netherlands", color: "#F97316" },
        away_team: { id: "japan", name: "Japan", color: "#BC002D" },
        served_visits_today: 340,
        peak_active_visitors: 900,
        peak_label: "18:30",
        revenue_estimate: 12400,
        dominant_nationality: "team_b",
        dominant_share: 60,
      },
    ],
  }),
  fetchZone: vi.fn().mockResolvedValue({
    entity_type: "stadium",
    zone_id: "stadium_zone",
    venue: { id: "stadium_zone", name: "AT&T Stadium", entity_type: "stadium", zone_id: "stadium_zone", lat: 32.7473, lng: -97.0945, comfort_capacity: 80000, kind: "stadium" },
    day: 0,
    scenario_id: "baseline",
    active_people_series_15m: [
      { step: 48, label: "18:00", value: 55000, marker: "kickoff" },
      { step: 50, label: "18:30", value: 72000, marker: "peak" },
    ],
    peak_active_people: 72000,
    peak: { step: 50, label: "18:30", active_people: 72000 },
    arrivals_series_15m: [{ step: 48, label: "18:00", value: 6000 }],
    departures_series_15m: [{ step: 48, label: "18:00", value: 2000 }],
    cumulative_entries: 82000,
    cumulative_exits: 76000,
    audience_mix: { team_a: 48, team_b: 37, neutral: 9, locals: 6 },
    wave_summary: { pre_match_peak: 52000, in_match_peak: 72000, post_match_peak: 41000 },
    top_inbound_corridors: [{ edge_id: "downtown_stadium", road_name: "I-30 Mainline", peak_load: 6400, peak_label: "17:45" }],
    metric_explanations: {
      active_people: { title: "Active people", definition: "People in venue", formula: "active_people_15m[t]", inputs: { peak_active_people: 72000 }, notes: [] },
      arrivals: { title: "Arrivals", definition: "Arrivals", formula: "max(0, active[t] - active[t-1])", inputs: { cumulative_entries: 82000 }, notes: [] },
      departures: { title: "Departures", definition: "Departures", formula: "max(0, active[t-1] - active[t])", inputs: { cumulative_exits: 76000 }, notes: [] },
    },
  }),
  createBusinessReport: vi.fn().mockResolvedValue({ job_id: "report-123", status: "queued" }),
  fetchReportJob: vi.fn().mockResolvedValue({ job_id: "report-123", status: "completed", download_url: "/api/reports/report-123/download" }),
  fetchProvenance: vi.fn().mockResolvedValue({
    generated_at: "2026-03-07T00:00:00Z",
    sources: [{ id: "seed_graph", label: "Road network graph", status: "hybrid_seeded", details: "Reduced planning graph." }],
    baseline_highlights: {},
    cohort_model: {},
  }),
}));

describe("App", () => {
  it("loads the dashboard, exposes playback speed, and opens a business drawer", async () => {
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: "Netherlands vs Japan" });
    expect(await screen.findByText("Top live district")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2x" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Select business" }));
    expect(await screen.findByText("Generate PDF report")).toBeInTheDocument();
    expect(screen.getByText("Active visitors over time")).toBeInTheDocument();
  });

  it("can switch to the stadium drawer", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Netherlands vs Japan" });
    await user.click(screen.getByRole("button", { name: "Select stadium" }));
    expect(await screen.findByText("Active people over time")).toBeInTheDocument();
    expect(screen.getByText("Top inbound corridors")).toBeInTheDocument();
  });

  it("can switch cities into schedule preview mode", async () => {
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: "Netherlands vs Japan" });
    await user.click(screen.getByRole("button", { name: /Monterrey/i }));

    expect(await screen.findByText("Schedule preview mode. This city is in the schedule registry, but the live map pack is not generated yet.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Poland vs Tunisia" })).toBeInTheDocument();
  });
});
