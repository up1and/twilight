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

// Get tile URL based on composite type
function getTileUrlForComposite(compositeType: CompositeType): string {
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
}

// Get attribution based on composite type
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
  const availableComposites: CompositeType[] = [
    "True Color",
    "IR Clouds",
    "Ash",
    "Water Vapor",
    "Dust",
  ];
  const [selectedComposites, setSelectedComposites] = useState<CompositeType[]>(
    ["True Color"]
  );

  const [serverSettings, setServerSettings] = useState({
    serverUrl: "https://example.com/api",
    apiKey: "",
  });
  const [mousePosition, setMousePosition] = useState<{
    lat: number;
    lng: number;
  } | null>(null);
  const isMobile = useIsMobile();

  // References to the tile layers
  const leftLayerRef = useRef<L.TileLayer | null>(null);
  const rightLayerRef = useRef<L.TileLayer | null>(null);

  // Track if we need to reset layer clipping
  const [resetClipping, setResetClipping] = useState(false);

  // Handle time change from TimeRangeSelector
  const handleTimeChange = (time: any) => {
    console.log("Selected time:", time.format());
    // Here you would update the map based on the selected time
  };

  // Update server settings
  const updateServerSettings = (newSettings: {
    serverUrl: string;
    apiKey: string;
  }) => {
    setServerSettings(newSettings);
    // Here you would update the tile URLs or other map settings based on the new server settings
  };

  // Handle mouse position change
  const handlePositionChange = (lat: number, lng: number) => {
    if (lat === 0 && lng === 0) {
      setMousePosition(null); // Hide when mouse leaves map
    } else {
      setMousePosition({ lat, lng });
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
          <SettingsButton
            settings={serverSettings}
            onSettingsChange={updateServerSettings}
          />
        </div>

        {/* TimeRangeSelector at the bottom */}
        <div className={`time-selector-container ${isMobile ? "mobile" : ""}`}>
          <TimeRangeSelector onTimeChange={handleTimeChange} />
        </div>
      </div>
    </main>
  );
}
