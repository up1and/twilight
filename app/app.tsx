import { useState, useRef, useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON, useMapEvents } from "react-leaflet";
import TimeRangeSelector from "./components/time-range-selector";
import SettingsButton from "./components/settings-button";
import MultiSelectComposite from "./components/multi-select-composite";
import CoordinatesDisplay from "./components/coordinates-display";
import SideBySide from "./components/side-by-side";
import { useIsMobile } from "./hooks/use-mobile";
import {
  getApiConfig,
  fetchLatestComposites,
  fetchTileJSON,
} from "./utils/api-client";
import "leaflet/dist/leaflet.css";
import "./app.css";
import type L from "leaflet";
import { LatLngTuple, CRS } from "leaflet";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import type { CompositeType, MapConfig } from "./utils/types";
import lands from "./natural-earth.json";

// Extend dayjs with UTC plugin
dayjs.extend(utc);

// Generate tile URL with time parameter
const generateTileUrl = (baseUrl: string, time: dayjs.Dayjs): string => {
  // Replace {time} placeholder with actual ISO 8601 time in UTC
  const timeStr = time.utc().format("YYYY-MM-DDTHH:mm:ss");
  return baseUrl.replace("{time}", timeStr);
};

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

export default function MapView() {
  // State for storing composites data from API (raw data)
  const [composites, setComposites] = useState<Record<string, string>>({});

  const [selectedComposites, setSelectedComposites] = useState<CompositeType[]>(
    ["true_color"]
  );

  const [selectedTime, setSelectedTime] = useState<dayjs.Dayjs>(dayjs());

  // Store map configurations for each selected composite
  const [mapConfigs, setMapConfigs] = useState<Record<string, MapConfig>>({});

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
    // Update map configs for all selected composites
    const updateMapConfigs = async () => {
      for (const composite of selectedComposites) {
        // if mapConfig has a corresponding composite name，fetchTileJSONForComposite is not called
        if (!mapConfigs[composite]) {
          await fetchTileJSONForComposite(composite);
        }
      }
    };

    updateMapConfigs();
  }, [selectedComposites, composites]);

  const position: LatLngTuple = [18, 110];
  const bounds: [LatLngTuple, LatLngTuple] = [
    [0, 70], // south west
    [55, 150], // north east
  ];

  return (
    <main style={{ height: "100vh", width: "100vw", overflow: "hidden" }}>
      <div className="map-container">
        {/* Map Container */}
        <MapContainer
          className="leaflet-map"
          center={position}
          zoom={6}
          maxBoundsViscosity={1.0}
          minZoom={mapConfigs[selectedComposites[0]]?.minZoom || 4}
          maxZoom={mapConfigs[selectedComposites[0]]?.maxZoom || 6}
          bounds={bounds}
          crs={CRS.EPSG3857}
          keyboard={false}
        >
          {/* First Layer */}
          <TileLayer
            url={tileUrl(selectedComposites[0])}
            ref={leftLayerRef}
            key={`${selectedComposites[0]}-${selectedTime.format()}`}
          />

          {/* Second Layer (only if two composites are selected) */}
          {selectedComposites.length > 1 && (
            <TileLayer
              url={tileUrl(selectedComposites[1])}
              ref={rightLayerRef}
              key={`${selectedComposites[1]}-${selectedTime.format()}`}
            />
          )}

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

          <GeoJSON
            data={lands as GeoJSON.GeoJsonObject}
            style={{
              color: "#828282",
              weight: 2,
              opacity: 1,
              fillOpacity: 0,
            }}
          />

          <MousePositionTracker onPositionChange={handlePositionChange} />
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
          <SettingsButton onSettingsChange={handleSettingsChange} />
        </div>

        {/* TimeRangeSelector at the bottom */}
        <div className={`time-selector-container ${isMobile ? "mobile" : ""}`}>
          <TimeRangeSelector
            onTimeChange={handleTimeChange}
            selectedTime={selectedTime}
          />
        </div>
      </div>
    </main>
  );
}
