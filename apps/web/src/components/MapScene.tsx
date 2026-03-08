import { useEffect, useMemo, useRef, useState } from "react";

import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { importLibrary, setOptions } from "@googlemaps/js-api-loader";

import type { EntityType, MetaResponse, SimulationSnapshotResponse } from "../lib/types";
import { formatCompact, formatPercent, titleCase } from "../lib/format";

type MapTypeKey = "roadmap" | "terrain" | "hybrid";
type LayerToggleKey = "corridors" | "districts" | "venues" | "specials" | "labels";
type VenueMode = "frontline" | "all" | "hotels";

interface HoverInfo {
  x: number;
  y: number;
  title: string;
  lines: string[];
}

interface MapSceneProps {
  meta: MetaResponse;
  snapshot: SimulationSnapshotResponse;
  selectedEntity: { type: EntityType; id: string } | null;
  onSelectEntity: (type: EntityType, id: string) => void;
}

let googleMapsBoot: Promise<void> | null = null;
let configuredGoogleKey = "";

function ensureGoogleMaps(apiKey: string): Promise<void> {
  if (!googleMapsBoot || configuredGoogleKey !== apiKey) {
    configuredGoogleKey = apiKey;
    setOptions({ key: apiKey, v: "weekly" });
    googleMapsBoot = importLibrary("maps").then(() => undefined);
  }
  return googleMapsBoot;
}

function edgeColor(congestion: number): [number, number, number, number] {
  if (congestion >= 0.75) return [220, 38, 38, 230];
  if (congestion >= 0.5) return [249, 115, 22, 228];
  if (congestion >= 0.25) return [250, 204, 21, 220];
  return [37, 99, 235, 205];
}

function zoneColor(utilization: number, alpha: number): [number, number, number, number] {
  if (utilization >= 1) return [249, 115, 22, alpha];
  if (utilization >= 0.75) return [245, 158, 11, alpha];
  if (utilization >= 0.4) return [59, 130, 246, alpha];
  return [148, 163, 184, alpha];
}

const ROADMAP_STYLES: google.maps.MapTypeStyle[] = [
  { featureType: "poi.business", stylers: [{ visibility: "off" }] },
  { featureType: "poi.park", stylers: [{ visibility: "off" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
  { featureType: "administrative.neighborhood", stylers: [{ visibility: "off" }] },
];

export function MapScene({ meta, snapshot, selectedEntity, onSelectEntity }: MapSceneProps) {
  const mapConfig = meta.map_config ?? {
    provider: "none" as const,
    google_maps_api_key: import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? null,
    default_map_type: "roadmap" as const,
    available_map_types: ["roadmap", "terrain", "hybrid"] as MapTypeKey[],
    initial_center: [-96.98, 32.78] as [number, number],
    initial_zoom: 9.5,
  };
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const overlayRef = useRef<GoogleMapsOverlay | null>(null);
  const [mapTypeId, setMapTypeId] = useState<MapTypeKey>(mapConfig.default_map_type);
  const [hoverInfo, setHoverInfo] = useState<HoverInfo | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [venueMode, setVenueMode] = useState<VenueMode>("frontline");
  const [visibleLayers, setVisibleLayers] = useState<Record<LayerToggleKey, boolean>>({
    corridors: true,
    districts: true,
    venues: true,
    specials: true,
    labels: true,
  });

  const edgePathById = useMemo(() => new globalThis.Map(meta.edges.map((edge) => [edge.id, edge.path])), [meta.edges]);
  const businessOverlayById = useMemo(
    () => new globalThis.Map(snapshot.business_overlay.map((item) => [item.business_id, item])),
    [snapshot.business_overlay],
  );
  const specialOverlayById = useMemo(
    () => new globalThis.Map(snapshot.special_overlay.map((item) => [item.entity_id, item])),
    [snapshot.special_overlay],
  );

  const businesses = useMemo(
    () =>
      meta.businesses.map((business) => ({
        ...business,
        value: businessOverlayById.get(business.id)?.value ?? 0,
        google_rating: businessOverlayById.get(business.id)?.google_rating ?? business.rating,
      })),
    [businessOverlayById, meta.businesses],
  );

  const visibleBusinesses = useMemo(() => {
    if (venueMode === "hotels") {
      return businesses.filter((business) => business.type === "hotel" || business.type === "hotel_bar");
    }
    if (venueMode === "frontline") {
      return businesses.filter((business) => business.type !== "hotel");
    }
    return businesses;
  }, [businesses, venueMode]);

  const specialVenues = useMemo(
    () =>
      meta.special_venues.map((venue) => ({
        ...venue,
        value: specialOverlayById.get(venue.id)?.value ?? 0,
        crowd_pressure: specialOverlayById.get(venue.id)?.crowd_pressure ?? 0,
      })),
    [meta.special_venues, specialOverlayById],
  );

  const layers = useMemo(() => {
    const layerList = [];

    if (visibleLayers.corridors) {
      layerList.push(
        new PathLayer({
          id: "roads-hitbox",
          data: snapshot.edges,
          pickable: true,
          widthUnits: "pixels",
          widthMinPixels: 18,
          getPath: (edge: (typeof snapshot.edges)[number]) => edgePathById.get(edge.edge_id) ?? [],
          getColor: [0, 0, 0, 0],
          getWidth: (edge: (typeof snapshot.edges)[number]) => 18 + edge.congestion * 20,
          onHover: (info) => {
            if (!info.object || typeof info.x !== "number" || typeof info.y !== "number") {
              setHoverInfo(null);
              return;
            }
            const edge = info.object as (typeof snapshot.edges)[number];
            setHoverInfo({
              x: info.x,
              y: info.y,
              title: edge.road_name,
              lines: [`Load ${formatCompact(edge.load)} / ${formatCompact(edge.capacity)}`, `Congestion ${formatPercent(edge.congestion)}`],
            });
          },
        }),
      );
      layerList.push(
        new PathLayer({
          id: "roads",
          data: snapshot.edges,
          pickable: false,
          widthUnits: "pixels",
          rounded: true,
          capRounded: true,
          jointRounded: true,
          widthMinPixels: 6,
          getPath: (edge: (typeof snapshot.edges)[number]) => edgePathById.get(edge.edge_id) ?? [],
          getColor: (edge: (typeof snapshot.edges)[number]) => edgeColor(edge.congestion),
          getWidth: (edge: (typeof snapshot.edges)[number]) => 5 + edge.congestion * 10,
        }),
      );
    }

    if (visibleLayers.districts) {
      layerList.push(
        new ScatterplotLayer({
          id: "districts",
          data: snapshot.zones,
          pickable: true,
          radiusUnits: "meters",
          opacity: 0.28,
          stroked: true,
          filled: true,
          getPosition: (zone: (typeof snapshot.zones)[number]) => zone.center,
          getRadius: 520,
          getFillColor: (zone: (typeof snapshot.zones)[number]) => zoneColor(zone.utilization, 84),
          getLineColor: (zone: (typeof snapshot.zones)[number]) => zoneColor(zone.utilization, 160),
          lineWidthMinPixels: 2,
          onHover: (info) => {
            if (!info.object || typeof info.x !== "number" || typeof info.y !== "number") {
              setHoverInfo(null);
              return;
            }
            const zone = info.object as (typeof snapshot.zones)[number];
            setHoverInfo({
              x: info.x,
              y: info.y,
              title: zone.name,
              lines: [`${formatCompact(zone.value)} visible people`, `Utilization ${formatPercent(zone.utilization)}`],
            });
          },
        }),
      );
    }

    if (visibleLayers.venues) {
      layerList.push(
        new ScatterplotLayer({
          id: "venues",
          data: visibleBusinesses,
          pickable: true,
          radiusUnits: "meters",
          stroked: true,
          filled: true,
          getPosition: (business: (typeof visibleBusinesses)[number]) => [business.lng, business.lat],
          getRadius: (business: (typeof visibleBusinesses)[number]) => 50 + Math.min(180, business.value * 0.07),
          getFillColor: (business: (typeof visibleBusinesses)[number]) =>
            selectedEntity?.id === business.id ? [234, 179, 8, 245] : business.type === "hotel" || business.type === "hotel_bar" ? [14, 165, 233, 220] : [244, 114, 182, 220],
          getLineColor: [255, 255, 255, 230],
          lineWidthMinPixels: 2,
          onHover: (info) => {
            if (!info.object || typeof info.x !== "number" || typeof info.y !== "number") {
              setHoverInfo(null);
              return;
            }
            const business = info.object as (typeof visibleBusinesses)[number];
            setHoverInfo({
              x: info.x,
              y: info.y,
              title: business.name,
              lines: [`${formatCompact(business.value)} active visitors`, `${titleCase(business.type)} | ${business.google_rating.toFixed(1)} stars`],
            });
          },
          onClick: (info) => {
            if (info.object) onSelectEntity("business", (info.object as (typeof visibleBusinesses)[number]).id);
          },
        }),
      );
    }

    if (visibleLayers.specials) {
      layerList.push(
        new ScatterplotLayer({
          id: "special-venues",
          data: specialVenues,
          pickable: true,
          radiusUnits: "meters",
          stroked: true,
          filled: true,
          getPosition: (venue: (typeof specialVenues)[number]) => [venue.lng, venue.lat],
          getRadius: (venue: (typeof specialVenues)[number]) => venue.entity_type === "stadium" ? 230 : 180,
          getFillColor: (venue: (typeof specialVenues)[number]) =>
            selectedEntity?.id === venue.id ? [250, 204, 21, 230] : venue.entity_type === "stadium" ? [15, 118, 110, 210] : [59, 130, 246, 210],
          getLineColor: [255, 255, 255, 220],
          lineWidthMinPixels: 3,
          onHover: (info) => {
            if (!info.object || typeof info.x !== "number" || typeof info.y !== "number") {
              setHoverInfo(null);
              return;
            }
            const venue = info.object as (typeof specialVenues)[number];
            setHoverInfo({
              x: info.x,
              y: info.y,
              title: venue.name,
              lines: [`${formatCompact(venue.value)} active people`, `Pressure ${formatPercent(venue.crowd_pressure)}`],
            });
          },
          onClick: (info) => {
            if (info.object) onSelectEntity((info.object as (typeof specialVenues)[number]).entity_type, (info.object as (typeof specialVenues)[number]).id);
          },
        }),
      );
    }

    if (visibleLayers.labels) {
      layerList.push(
        new TextLayer({
          id: "district-labels",
          data: snapshot.zones.slice(0, 5).map((zone) => ({
            id: zone.zone_id,
            position: zone.center,
            text: `${zone.name}\n${formatCompact(zone.value)}`,
          })),
          pickable: false,
          background: true,
          getPosition: (item: { position: [number, number] }) => item.position,
          getText: (item: { text: string }) => item.text,
          getColor: [15, 23, 42, 255],
          getBackgroundColor: [255, 255, 255, 214],
          backgroundPadding: [6, 4],
          sizeUnits: "pixels",
          getSize: 12,
          getTextAnchor: "middle",
          getAlignmentBaseline: "bottom",
          getPixelOffset: [0, -18],
        }),
      );
    }

    return layerList;
  }, [edgePathById, onSelectEntity, selectedEntity?.id, snapshot.edges, snapshot.zones, snapshot.business_overlay, specialVenues, visibleBusinesses, visibleLayers]);

  useEffect(() => {
    const apiKey = mapConfig.google_maps_api_key;
    if (!apiKey || !containerRef.current) {
      setMapError("Google Maps API key missing. The basemap cannot load.");
      return;
    }

    let cancelled = false;
    ensureGoogleMaps(apiKey)
      .then(async () => {
        if (cancelled || !containerRef.current) return;
        const mapsLibrary = (await importLibrary("maps")) as google.maps.MapsLibrary;
        if (!mapRef.current) {
          mapRef.current = new mapsLibrary.Map(containerRef.current, {
            center: { lng: mapConfig.initial_center[0], lat: mapConfig.initial_center[1] },
            zoom: mapConfig.initial_zoom,
            mapTypeId,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: false,
            rotateControl: false,
            clickableIcons: false,
            gestureHandling: "greedy",
            styles: ROADMAP_STYLES,
          });
        }
        if (!overlayRef.current) {
          overlayRef.current = new GoogleMapsOverlay({ layers, interleaved: true, pickingRadius: 12 });
          overlayRef.current.setMap(mapRef.current);
        } else {
          overlayRef.current.setProps({ layers, pickingRadius: 12 });
        }
        mapRef.current.setMapTypeId(mapTypeId);
        setMapError(null);
      })
      .catch((reason: Error) => {
        if (!cancelled) setMapError(reason.message);
      });

    return () => {
      cancelled = true;
    };
  }, [layers, mapConfig.google_maps_api_key, mapConfig.initial_center, mapConfig.initial_zoom, mapTypeId]);

  useEffect(() => {
    return () => {
      overlayRef.current?.setMap(null);
      overlayRef.current?.finalize();
      overlayRef.current = null;
      mapRef.current = null;
    };
  }, []);

  const toggleLayer = (layer: LayerToggleKey) => {
    setVisibleLayers((current) => ({ ...current, [layer]: !current[layer] }));
  };

  return (
    <section className="map-shell">
      <div ref={containerRef} className="google-map-surface" />
      <div className="map-overlay-panel top">
        <p className="eyebrow">Live map</p>
        <strong>{snapshot.summary.busiest_zone.name}</strong>
        <span>
          {snapshot.summary.weather.condition} | {snapshot.summary.weather.temp_c}C
        </span>
        <div className="chip-row map-mode-row">
          {mapConfig.available_map_types.map((mode) => (
            <button key={mode} type="button" className={mode === mapTypeId ? "chip active" : "chip"} onClick={() => setMapTypeId(mode)}>
              {mode === "roadmap" ? "Road" : mode === "terrain" ? "Terrain" : "Hybrid"}
            </button>
          ))}
        </div>
      </div>

      <div className="map-overlay-panel bottom">
        <div className="section-header compact">
          <h3>Layers</h3>
          <span className="stat-footnote">Map detail</span>
        </div>
        <div className="chip-row">
          {(["corridors", "districts", "venues", "specials", "labels"] as LayerToggleKey[]).map((layer) => (
            <button key={layer} type="button" className={visibleLayers[layer] ? "chip active" : "chip"} onClick={() => toggleLayer(layer)}>
              {titleCase(layer)}
            </button>
          ))}
        </div>
        <div className="section-header compact">
          <h3>Venue filter</h3>
          <span className="stat-footnote">Businesses on map</span>
        </div>
        <div className="chip-row">
          <button type="button" className={venueMode === "frontline" ? "chip active" : "chip"} onClick={() => setVenueMode("frontline")}>
            Frontline
          </button>
          <button type="button" className={venueMode === "all" ? "chip active" : "chip"} onClick={() => setVenueMode("all")}>
            All venues
          </button>
          <button type="button" className={venueMode === "hotels" ? "chip active" : "chip"} onClick={() => setVenueMode("hotels")}>
            Hotels
          </button>
        </div>
      </div>

      {hoverInfo ? (
        <div className="map-tooltip" style={{ left: hoverInfo.x + 18, top: hoverInfo.y + 18 }}>
          <strong>{hoverInfo.title}</strong>
          {hoverInfo.lines.map((line) => (
            <span key={line}>{line}</span>
          ))}
        </div>
      ) : null}
      {mapError ? <div className="map-error-banner">{mapError}</div> : null}
    </section>
  );
}
