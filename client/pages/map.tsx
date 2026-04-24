import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { MapContainer, useMapEvents, useMap } from "react-leaflet";
import type L from "leaflet";
import { CRS } from "leaflet";
import "leaflet.vectorgrid";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";

import TimeDimensionLayer, {
  type TimeDimensionLayerHandles
} from "../components/time-dimension-layer";
import TimeRangeSelector from "../components/time-range-selector";
import MultiSelectComposite from "../components/multi-select-composite";
import CoordinatesDisplay from "../components/coordinates-display";
import Legend from "../components/legend";
import SideBySide from "../components/side-by-side";
import SnapshotButton from "../components/snapshot-button";
import LayerButton from "../components/layer-button";
import { useIsMobile } from "../hooks/use-mobile";
import { fetchLatestComposites, fetchTileJSON, fetchLegend } from "../utils/api-client";
import { roundToNearestTenMinutes } from "../utils/time-utils";

import type { CompositeType, MapConfig, MapLayers } from "../utils/types";

import "leaflet/dist/leaflet.css";
import "./map.css";

// Extend dayjs with UTC plugin
dayjs.extend(utc);

// VectorGrid Layer component with overzooming support
function VectorGridLayer({
  url,
  styles
}: {
  url: string;
  styles: { [layerName: string]: any };
}) {
  const map = useMap();

  useEffect(() => {
    if (!map) return;

    // Check if vectorGrid is available
    if (!(window.L as any)?.vectorGrid?.protobuf) {
      console.error("Leaflet VectorGrid plugin is not loaded");
      return;
    }

    try {
      // Create vector grid layer with overzooming support
      const vectorGridLayer = (window.L as any).vectorGrid.protobuf(url, {
        vectorTileLayerStyles: styles,
        interactive: false,
        // Add overzooming support - use zoom 6 data for zoom levels 7-10
        maxNativeZoom: 6,
        maxZoom: 10,
        // Add caching to prevent re-requests
        updateWhenIdle: true,
        updateWhenZooming: false,
        // Set z-index to display above tile layers
        zIndex: 800
      });

      // Add layer to map
      map.addLayer(vectorGridLayer);

      // Cleanup function
      return () => {
        if (map.hasLayer(vectorGridLayer)) {
          map.removeLayer(vectorGridLayer);
        }
      };
    } catch (error) {
      console.error("Error creating VectorGrid layer:", error);
    }
  }, [map, url]); // Only depend on map and url

  return null;
}

// Mouse position tracker component
function MousePositionTracker({
  onPositionChange
}: {
  onPositionChange: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    mousemove: (e) => {
      onPositionChange(e.latlng.lat, e.latlng.lng);
    },
    mouseout: () => {
      onPositionChange(0, 0); // Reset or hide when mouse leaves map
    }
  });
  return null;
}

// Map viewport bounds tracker component
function MapViewportBoundsTracker({
  onBoundsChange
}: {
  onBoundsChange: (bounds: [number, number, number, number]) => void;
}) {
  const map = useMap();

  useEffect(() => {
    if (!map) return;

    const updateBounds = () => {
      const bounds = map.getBounds();
      const bbox: [number, number, number, number] = [
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth()
      ];
      onBoundsChange(bbox);
    };

    // Update bounds initially
    updateBounds();

    // Update bounds when map moves or zooms
    map.on("moveend", updateBounds);
    map.on("zoomend", updateBounds);

    return () => {
      map.off("moveend", updateBounds);
      map.off("zoomend", updateBounds);
    };
  }, [map]);

  return null;
}

// Map bounds updater component
function MapBoundsUpdater({
  bounds
}: {
  bounds: L.LatLngBoundsExpression | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (!map || !bounds) return;

    try {
      // Set max bounds to prevent dragging outside
      map.setMaxBounds(bounds);
    } catch (error) {
      console.error("Error setting map bounds:", error);
    }
  }, [map, bounds]);

  return null;
}

export default function MapView() {
  // State for storing composites data from API (raw data)
  const [composites, setComposites] = useState<Record<string, string>>({});

  const [selectedComposites, setSelectedComposites] = useState<CompositeType[]>(
    () => {
      const saved = localStorage.getItem("selected-composites");
      return saved ? JSON.parse(saved) : ["true_color"];
    }
  );

  const [layers, setLayers] = useState<MapLayers>(() => {
    const boundary = localStorage.getItem("fir-boundary");
    return {
      "fir-boundary": boundary ? JSON.parse(boundary) : false
    };
  });

  const [selectedTime, setSelectedTime] = useState<dayjs.Dayjs>(
    roundToNearestTenMinutes(dayjs().utc())
  );
  const [timelineTime, setTimelineTime] = useState<dayjs.Dayjs>(
    roundToNearestTenMinutes(dayjs().utc())
  );
  const [viewportBounds, setViewportBounds] = useState<
    [number, number, number, number] | null
  >(null);

  // Store map configurations for each selected composite
  const [mapConfigs, setMapConfigs] = useState<Record<string, MapConfig>>({});

  // Store legend data for each composite
  const [legendData, setLegendData] = useState<
    Record<string, { color: string; label: string }[]>
  >({});

  // Fixed zoom levels and center
  const center: [number, number] = [27.5, 117.5];
  const minZoom = 5;
  const maxZoom = 10;
  const defaultZoom = 6;

  // No longer need to store endpoint and token in component state
  const [mousePosition, setMousePosition] = useState<{
    lat: number;
    lng: number;
  } | null>(null);

  const isMobile = useIsMobile();

  // References to the TimeDimensionLayer handles
  const leftLayerRef = useRef<TimeDimensionLayerHandles | null>(null);
  const rightLayerRef = useRef<TimeDimensionLayerHandles | null>(null);

  // Track buffering state for each layer
  const [layerBufferingStates, setLayerBufferingStates] = useState<
    Record<string, boolean>
  >({});

  // Toggles layer state, auto-syncs to localStorage using layerId as key
  const toggleLayer = (layerId: keyof MapLayers) => {
    const newValue = !layers[layerId];
    console.log(`Layer changed: ${layerId} -> ${newValue}`);
    setLayers({
      ...layers,
      [layerId]: newValue,
    });
    localStorage.setItem(layerId, JSON.stringify(newValue));
  };

  // Get the composite's bounds
  const compositeBounds = useMemo(() => {
    return selectedComposites.length > 0 && mapConfigs[selectedComposites[0]]
      ? mapConfigs[selectedComposites[0]].bounds
      : null;
  }, [selectedComposites, mapConfigs]);

  // Calculate timedelta for video generation
  const videoTimedelta = useMemo(() => {
    return timelineTime.diff(selectedTime, "minute");
  }, [timelineTime, selectedTime]);

  // Calculate overall buffering state
  const isBuffering = useMemo(() => {
    return Object.values(layerBufferingStates).some((state) => state);
  }, [layerBufferingStates]);

  // Handle buffering state change for a specific layer
  const handleLayerBufferingChange = useCallback(
    (layerId: string, isBuffering: boolean) => {
      setLayerBufferingStates((prev) => ({
        ...prev,
        [layerId]: isBuffering
      }));
    },
    []
  );

  // Get the latest update time for selected composites
  const latestCompositeTime = useMemo(() => {
    // Filter selected composites that have valid (non-null) timestamps
    const selectedTimestamps = selectedComposites
      .filter(
        (composite) => composite in composites && composites[composite] !== null
      )
      .map((composite) => dayjs(composites[composite]));

    if (selectedTimestamps.length > 0) {
      // Use earliest time from selected composites if available
      return selectedTimestamps.reduce((earliest, current) =>
        current.isBefore(earliest) ? current : earliest
      );
    }
  }, [composites, selectedComposites]);

  // Fetch TileJSON data for a specific composite
  const fetchTileJSONForComposite = async (composite: CompositeType) => {
    // Get the original key from formatted name
    if (!composite) {
      console.error(`Could not find original key for composite: ${composite}`);
      return null;
    }

    try {
      // Fetch TileJSON data
      const tileJson = await fetchTileJSON(composite);

      if (tileJson) {
        // Create a MapConfig from TileJSON data
        const mapConfig: MapConfig = {
          bounds: tileJson.bounds
            ? [
                [tileJson.bounds[1], tileJson.bounds[0]],
                [tileJson.bounds[3], tileJson.bounds[2]]
              ]
            : null,
          minZoom: tileJson.minzoom || 1,
          maxZoom: tileJson.maxzoom || 18,
          tileUrl: tileJson.tiles[0],
          attribution: tileJson.attribution || ""
        };

        // Update mapConfigs state
        setMapConfigs((prev) => ({
          ...prev,
          [composite]: mapConfig
        }));

        return mapConfig;
      }
    } catch (error) {
      console.error(`Error fetching TileJSON for ${composite}:`, error);
    }

    // Return a default config if TileJSON fetch fails
    return null;
  };

  // Handle time change from TimeRangeSelector
  const handleTimeChange = (time: any) => {
    setSelectedTime(time);
  };

  // Handle time range change from TimeRangeSelector
  const handleTimeRangeChange = (
    _startTime: dayjs.Dayjs,
    endTime: dayjs.Dayjs
  ) => {
    setTimelineTime(endTime);
  };

  // Handle current viewport bounds change
  const handleViewportBoundsChange = (
    bbox: [number, number, number, number]
  ) => {
    setViewportBounds(bbox);
  };

  // Handle mouse position change
  const handlePositionChange = (lat: number, lng: number) => {
    if (lat === 0 && lng === 0) {
      setMousePosition(null); // Hide when mouse leaves map
    } else {
      setMousePosition({ lat, lng });
    }
  };

  // Get tile URL template based on composite type
  const tileUrlTemplate = (composite: CompositeType): string =>
    mapConfigs[composite]?.tileUrl ?? "";

  // Handle composite selection change
  const handleCompositeChange = (selected: CompositeType[]) => {
    // Ensure at least one option is always selected
    if (selected.length === 0) {
      return;
    }
    setSelectedComposites(selected);
    // Save selected composites to local storage
    localStorage.setItem("selected-composites", JSON.stringify(selected));
  };

  // Fetch latest composites on component mount and every minute
  useEffect(() => {
    // Function to fetch composites
    const fetchComposites = async () => {
      try {
        const data = await fetchLatestComposites();
        setComposites(data);
        console.log("latest composites:", data);
      } catch (error) {
        console.error("error fetching composites:", error);
      }
    };

    // Fetch immediately on mount
    fetchComposites();

    // Set up interval to fetch every minute
    const intervalId = setInterval(fetchComposites, 60000);

    // Clean up interval on component unmount
    return () => clearInterval(intervalId);
  }, []);

  useEffect(() => {
    if (latestCompositeTime && !latestCompositeTime.isSame(selectedTime)) {
      const diffMinutes = selectedTime.diff(latestCompositeTime, "minute");

      if (diffMinutes > -30) {
        console.log(
          `selected time is ${diffMinutes} minutes behind latest data, resetting to latest composite time.`
        );
        setSelectedTime(latestCompositeTime);
      }
    }
  }, [latestCompositeTime]);

  // Update map configurations when selected composites change
  useEffect(() => {
    const updateMapConfigs = async () => {
      for (const composite of selectedComposites) {
        if (!mapConfigs[composite]) {
          await fetchTileJSONForComposite(composite);
        }
      }
    };

    updateMapConfigs();
  }, [selectedComposites, composites]);

  // Fetch legend data when selected composites change
  useEffect(() => {
    const fetchLegendData = async () => {
      for (const composite of selectedComposites) {
        if (!legendData[composite]) {
          const data = await fetchLegend(composite);
          if (data) {
            setLegendData((prev) => ({
              ...prev,
              [composite]: data
            }));
          }
        }
      }
    };

    fetchLegendData();
  }, [selectedComposites]);

  return (
    <main style={{ height: "100vh", width: "100vw", overflow: "hidden" }}>
      <div className="map-container">
        {/* Map Container */}
        <MapContainer
          className="leaflet-map"
          center={center}
          zoom={defaultZoom}
          minZoom={minZoom}
          maxZoom={maxZoom}
          maxBoundsViscosity={1.0}
          crs={CRS.EPSG3857}
          keyboard={false}
        >
          {/* Map bounds updater */}
          <MapBoundsUpdater bounds={compositeBounds} />

          {/* First Layer */}
          <TimeDimensionLayer
            currentTime={selectedTime}
            timelineTime={timelineTime}
            urlTemplate={tileUrlTemplate(selectedComposites[0])}
            attribution={mapConfigs[selectedComposites[0]]?.attribution}
            ref={leftLayerRef}
            bounds={compositeBounds || undefined}
            onBufferingChange={(isBuffering) =>
              handleLayerBufferingChange("left", isBuffering)
            }
          />

          {/* Second Layer (only if two composites are selected) */}
          {selectedComposites.length > 1 && (
            <TimeDimensionLayer
              currentTime={selectedTime}
              timelineTime={timelineTime}
              urlTemplate={tileUrlTemplate(selectedComposites[1])}
              attribution={mapConfigs[selectedComposites[1]]?.attribution}
              ref={rightLayerRef}
              bounds={compositeBounds || undefined}
              onBufferingChange={(isBuffering) =>
                handleLayerBufferingChange("right", isBuffering)
              }
            />
          )}

          {/* VectorGrid Layer */}
          <VectorGridLayer
            url="/tiles/lands/{z}/{x}/{y}.pbf"
            styles={{
              land: {
                color: "#828282",
                weight: 1.5,
                fillOpacity: 0
              }
            }}
          />

          {layers["fir-boundary"] && (
            <VectorGridLayer
              url="/tiles/firs/{z}/{x}/{y}.pbf"
              styles={{
                fir: {
                  color: "#a1a1a1",
                  weight: 1,
                  fillOpacity: 0,
                  opacity: 0.5
                }
              }}
            />
          )}

          {/* Side-by-side control - only show if two layers are selected */}
          {selectedComposites.length > 1 &&
            leftLayerRef.current &&
            rightLayerRef.current && (
              <SideBySide
                leftLayer={leftLayerRef.current}
                rightLayer={rightLayerRef.current}
                selectedTime={selectedTime}
                initialPosition={50}
              />
            )}

          <MousePositionTracker onPositionChange={handlePositionChange} />
          <MapViewportBoundsTracker
            onBoundsChange={handleViewportBoundsChange}
          />
        </MapContainer>

        {/* Coordinates Display */}
        {mousePosition && (
          <CoordinatesDisplay lat={mousePosition.lat} lng={mousePosition.lng} />
        )}

        {/* Legend for single composite - bottom right only */}
        {selectedComposites.length === 1 &&
          legendData[selectedComposites[0]] && (
            <div className="legend-position-right">
              <Legend
                items={legendData[selectedComposites[0]]}
                defaultExpanded={false}
              />
            </div>
          )}

        {/* Legends for side-by-side mode - left and right */}
        {selectedComposites.length > 1 && (
          <>
            {legendData[selectedComposites[0]] && (
              <div className="legend-position-left">
                <Legend
                  items={legendData[selectedComposites[0]]}
                  defaultExpanded={false}
                />
              </div>
            )}
            {legendData[selectedComposites[1]] && (
              <div className="legend-position-right">
                <Legend
                  items={legendData[selectedComposites[1]]}
                  defaultExpanded={false}
                />
              </div>
            )}
          </>
        )}

        {/* Controls Overlay */}
        <div className="map-controls">
          <MultiSelectComposite
            options={Object.keys(composites)}
            selectedOptions={selectedComposites}
            onChange={handleCompositeChange}
            maxSelections={2}
          />
          <SnapshotButton
            composites={selectedComposites}
            selectedTime={selectedTime}
            bbox={viewportBounds}
            timedelta={videoTimedelta}
          />
          <LayerButton layers={layers} onToggle={toggleLayer} />
        </div>

        {/* TimeRangeSelector at the bottom */}
        <div className={`time-selector-container ${isMobile ? "mobile" : ""}`}>
          <TimeRangeSelector
            selectedTime={selectedTime}
            latestCompositeTime={latestCompositeTime}
            onSelectedTimeChange={handleTimeChange}
            onTimeRangeChange={handleTimeRangeChange}
            isBuffering={isBuffering}
          />
        </div>
      </div>
    </main>
  );
}
