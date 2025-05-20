import { useState, useRef, useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  ZoomControl,
  useMapEvents,
} from "react-leaflet";
import TimeRangeSelector from "./components/time-range-selector";
import SettingsButton from "./components/settings-button";
import MultiSelectComposite from "./components/multi-select-composite";
import CoordinatesDisplay from "./components/coordinates-display";
import SideBySide from "./components/side-by-side";
import { useIsMobile } from "./hooks/use-mobile";
import {
  getApiConfig,
  fetchLatestComposites,
  formatCompositeName,
} from "./utils/api-client";
import "leaflet/dist/leaflet.css";
import "./app.css";
import type L from "leaflet";

import type { CompositeType } from "./utils/types";

// Default tile URL templates
const DEFAULT_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

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

// Default attribution based on composite type
function getAttributionForComposite(compositeType: CompositeType): string {
  switch (compositeType) {
    case "True Color":
    case "IR Clouds":
      return '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
    case "Ash":
    case "Water Vapor":
    case "Dust":
      return '&copy; <a href="https://carto.com/attributions">CARTO</a>';
    default:
      return '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  }
}

export default function MapView() {
  // State for storing composites data from API (raw data)
  const [compositesData, setCompositesData] = useState<Record<string, string>>(
    {}
  );

  // State for storing formatted composite names for UI display
  const [availableComposites, setAvailableComposites] = useState<
    CompositeType[]
  >([]);

  const [selectedComposites, setSelectedComposites] = useState<CompositeType[]>(
    ["True Color"]
  );

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
      try {
        const data = await fetchLatestComposites();
        setCompositesData(data);

        // Update available composites with formatted names
        if (Object.keys(data).length > 0) {
          const formattedComposites = Object.keys(data).map(
            (key) => formatCompositeName(key) as CompositeType
          );
          setAvailableComposites(formattedComposites);
        }

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

  // Handle time change from TimeRangeSelector
  const handleTimeChange = (time: any) => {
    console.log("selected time:", time.format());
    // Here you would update the map based on the selected time
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
  const getTileUrlForComposite = (compositeType: CompositeType): string => {
    // Get the original key from formatted name
    const getOriginalKey = (formattedName: string): string => {
      for (const key of Object.keys(compositesData)) {
        if (formatCompositeName(key) === formattedName) {
          return key;
        }
      }
      return "";
    };

    // Try to get the original key from compositesData
    const originalKey = getOriginalKey(compositeType);

    // If we have data for this composite, construct a URL with the endpoint
    if (originalKey && compositesData[originalKey]) {
      const { endpoint } = getApiConfig();
      return `${endpoint}/tiles/${originalKey}/{z}/{x}/{y}.png`;
    }

    // Fallback to static URLs if no data is available
    switch (compositeType) {
      case "True Color":
        return DEFAULT_TILE_URL;
      case "IR Clouds":
        // In a real app, these would be actual URLs to your tile services
        return "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
      case "Ash":
        return "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png";
      case "Water Vapor":
        return "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png";
      case "Dust":
        return "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png";
      default:
        return DEFAULT_TILE_URL;
    }
  };

  // Handle composite selection change
  const handleCompositeChange = (selected: CompositeType[]) => {
    // Ensure at least one option is always selected
    if (selected.length === 0) {
      return;
    }

    // If we're going from 2 layers to 1 layer, we need to reset clipping
    if (selectedComposites.length === 2 && selected.length === 1) {
      setResetClipping(true);
    }

    setSelectedComposites(selected);
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

  return (
    <main style={{ height: "100vh", width: "100vw", overflow: "hidden" }}>
      <div className="map-container">
        {/* Map Container */}
        <MapContainer
          center={[51.505, -0.09]}
          zoom={13}
          zoomControl={false} // We'll add our own zoom control
          className="leaflet-map"
        >
          {/* First Layer */}
          {selectedComposites.length > 0 && (
            <TileLayer
              attribution={getAttributionForComposite(selectedComposites[0])}
              url={getTileUrlForComposite(selectedComposites[0])}
              ref={leftLayerRef}
            />
          )}

          {/* Second Layer (only if two composites are selected) */}
          {selectedComposites.length > 1 && (
            <TileLayer
              attribution={getAttributionForComposite(selectedComposites[1])}
              url={getTileUrlForComposite(selectedComposites[1])}
              ref={rightLayerRef}
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

          <ZoomControl position="topleft" />
          <MousePositionTracker onPositionChange={handlePositionChange} />
        </MapContainer>

        {/* Coordinates Display */}
        {mousePosition && (
          <CoordinatesDisplay lat={mousePosition.lat} lng={mousePosition.lng} />
        )}

        {/* Controls Overlay */}
        <div className="map-controls">
          <MultiSelectComposite
            options={availableComposites}
            selectedOptions={selectedComposites}
            onChange={handleCompositeChange}
            maxSelections={2}
          />
          <SettingsButton onSettingsChange={handleSettingsChange} />
        </div>

        {/* TimeRangeSelector at the bottom */}
        <div className={`time-selector-container ${isMobile ? "mobile" : ""}`}>
          <TimeRangeSelector onTimeChange={handleTimeChange} />
        </div>
      </div>
    </main>
  );
}
