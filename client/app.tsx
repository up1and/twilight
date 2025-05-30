import { useState, useRef, useEffect } from "react";
import { MapContainer, TileLayer, useMapEvents, useMap } from "react-leaflet";
import TimeRangeSelector from "./components/time-range-selector";
import SettingsButton from "./components/settings-button";
import MultiSelectComposite from "./components/multi-select-composite";
import CoordinatesDisplay from "./components/coordinates-display";
import SideBySide from "./components/side-by-side";
import SnapshotButton from "./components/snapshot-button";
import { useIsMobile } from "./hooks/use-mobile";
import {
  getApiConfig,
  fetchLatestComposites,
  fetchTileJSON,
} from "./utils/api-client";
import "leaflet/dist/leaflet.css";
import "./app.css";
import type L from "leaflet";
import { CRS } from "leaflet";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import type { CompositeType, MapConfig } from "./utils/types";

import "leaflet.vectorgrid";

// Extend dayjs with UTC plugin
dayjs.extend(utc);

// Generate tile URL with time parameter
const generateTileUrl = (baseUrl: string, time: dayjs.Dayjs): string => {
  // Replace {time} placeholder with actual ISO 8601 time in UTC
  const timeStr = time.utc().format("YYYY-MM-DDTHH:mm:ss");
  return baseUrl.replace("{time}", timeStr);
};

// VectorGrid Layer component with overzooming support
function VectorGridLayer({
  url,
  styles,
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
        zIndex: 800,
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
  onPositionChange,
}: {
  onPositionChange: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    mousemove: (e) => {
      onPositionChange(e.latlng.lat, e.latlng.lng);
    },
    mouseout: () => {
      onPositionChange(0, 0); // Reset or hide when mouse leaves map
    },
  });
  return null;
}

// Map viewport bounds tracker component
function MapViewportBoundsTracker({
  onBoundsChange,
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
        bounds.getNorth(),
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
  bounds,
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
    ["true_color"]
  );

  const [selectedTime, setSelectedTime] = useState<dayjs.Dayjs>(dayjs());
  const [timeRangeEnd, setTimeRangeEnd] = useState<dayjs.Dayjs>(dayjs());
  const [viewportBounds, setViewportBounds] = useState<
    [number, number, number, number] | null
  >(null);

  // Store map configurations for each selected composite
  const [mapConfigs, setMapConfigs] = useState<Record<string, MapConfig>>({});

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

  // Fetch latest composites on component mount and every minute
  useEffect(() => {
    // Function to fetch composites
    const fetchComposites = async () => {
      const now = dayjs();
      const diff = now.diff(selectedTime);
      if (diff > 3600000) {
        return;
      }
      try {
        const data = await fetchLatestComposites();
        const timestamps = selectedComposites
          .filter((composite) => composite in data)
          .map((composite) => dayjs(data[composite]));
        const earliestTime = timestamps.reduce((earliest, current) =>
          current.isBefore(earliest) ? current : earliest
        );
        setComposites(data);
        setSelectedTime(earliestTime);
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

  // References to the tile layers
  const leftLayerRef = useRef<L.TileLayer | null>(null);
  const rightLayerRef = useRef<L.TileLayer | null>(null);

  // Track if we need to reset layer clipping
  const [resetClipping, setResetClipping] = useState(false);

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
                [tileJson.bounds[3], tileJson.bounds[2]],
              ]
            : null,
          minZoom: tileJson.minzoom || 1,
          maxZoom: tileJson.maxzoom || 18,
          tileUrl: tileJson.tiles[0],
          attribution: tileJson.attribution || "",
        };

        // Update mapConfigs state
        setMapConfigs((prev) => ({
          ...prev,
          [composite]: mapConfig,
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
    console.log("selected time:", time.format());
    setSelectedTime(time);
  };

  // Handle time range change from TimeRangeSelector
  const handleTimeRangeChange = (
    _startTime: dayjs.Dayjs,
    endTime: dayjs.Dayjs
  ) => {
    setTimeRangeEnd(endTime);
  };

  // Calculate timedelta for video generation
  const calculateTimedelta = (): number => {
    return timeRangeEnd.diff(selectedTime, "minute");
  };

  // Handle current viewport bounds change
  const handleViewportBoundsChange = (
    bbox: [number, number, number, number]
  ) => {
    setViewportBounds(bbox);
  };

  // Callback function when settings change
  const handleSettingsChange = () => {
    // Add any logic that needs to run after settings are updated
    console.log("settings updated:", getApiConfig());
  };

  // Handle mouse position change
  const handlePositionChange = (lat: number, lng: number) => {
    if (lat === 0 && lng === 0) {
      setMousePosition(null); // Hide when mouse leaves map
    } else {
      setMousePosition({ lat, lng });
    }
  };

  // Get tile URL based on composite type
  const tileUrl = (composite: CompositeType): string => {
    // First check if we have a mapConfig for this composite
    if (mapConfigs[composite]) {
      return generateTileUrl(mapConfigs[composite].tileUrl, selectedTime);
    }
    return "";
  };

  // Handle composite selection change
  const handleCompositeChange = (selected: CompositeType[]) => {
    // Ensure at least one option is always selected
    if (selected.length === 0) {
      return;
    }
    setSelectedComposites(selected);
    console.log(tileUrl(selectedComposites[0]));
  };

  // Reset clipping when going from 2 layers to 1 layer
  useEffect(() => {
    if (resetClipping && leftLayerRef.current) {
      // Reset the clipping on the remaining layer
      const leftLayerElement = (leftLayerRef.current as any)._container;
      if (leftLayerElement) {
        leftLayerElement.style.clip = "auto";
      }

      setResetClipping(false);
    }
  }, [resetClipping, selectedComposites]);

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

  // Get the composite's bounds
  const compositeBounds =
    selectedComposites.length > 0 && mapConfigs[selectedComposites[0]]
      ? mapConfigs[selectedComposites[0]].bounds
      : null;

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
          <TileLayer
            url={tileUrl(selectedComposites[0])}
            ref={leftLayerRef}
            key={`${selectedComposites[0]}-${selectedTime.format()}`}
            noWrap={true}
            bounds={compositeBounds || undefined}
          />

          {/* Second Layer (only if two composites are selected) */}
          {selectedComposites.length > 1 && (
            <TileLayer
              url={tileUrl(selectedComposites[1])}
              ref={rightLayerRef}
              key={`${selectedComposites[1]}-${selectedTime.format()}`}
              noWrap={true}
              bounds={compositeBounds || undefined}
            />
          )}

          {/* VectorGrid Layer */}
          <VectorGridLayer
            url={`${getApiConfig().endpoint}/lands/{z}/{x}/{y}.pbf`}
            styles={{
              land: {
                color: "#828282",
                weight: 1.5,
                fillOpacity: 0,
              },
            }}
          />

          {/* Side-by-side control - only show if two layers are selected */}
          {selectedComposites.length > 1 &&
            leftLayerRef.current &&
            rightLayerRef.current && (
              <SideBySide
                leftLayer={leftLayerRef.current}
                rightLayer={rightLayerRef.current}
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
            timedelta={calculateTimedelta()}
          />
          <SettingsButton onSettingsChange={handleSettingsChange} />
        </div>

        {/* TimeRangeSelector at the bottom */}
        <div className={`time-selector-container ${isMobile ? "mobile" : ""}`}>
          <TimeRangeSelector
            onTimeChange={handleTimeChange}
            selectedTime={selectedTime}
            onTimeRangeChange={handleTimeRangeChange}
          />
        </div>
      </div>
    </main>
  );
}
