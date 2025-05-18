import { useState, useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  useMapEvent,
  useMap,
} from "react-leaflet";
import { LatLngTuple, CRS } from "leaflet";
import ky from "ky";
import dayjs from "dayjs";

import Control from "./components/Control";
import TimeRangeSelector from "./components/time-range-selector";
import SettingModal from "./components/Setting";
import { CompositeType, MapConfig, TileJSON } from "./utils/types";
import lands from "./natural-earth.json";
import firs from "./firs.json";

import "leaflet/dist/leaflet.css";

const MousePosition: React.FC = () => {
  const [position, setPosition] = useState<{ lat: number; lng: number } | null>(
    null
  );

  useMapEvent("mousemove", (e) => {
    setPosition({ lat: e.latlng.lat, lng: e.latlng.lng });
  });

  useMapEvent("mouseout", () => {
    setPosition(null);
  });

  return (
    <div>
      {position && (
        <div className="text-stroke">
          {position.lat.toFixed(4)}, {position.lng.toFixed(4)}
        </div>
      )}
    </div>
  );
};

const MapConfigUpdater: React.FC<{
  mapConfig: MapConfig;
}> = ({ mapConfig }) => {
  const map = useMap();

  useEffect(() => {
    if (mapConfig.bounds) {
      map.setMaxBounds(mapConfig.bounds);
      map.fitBounds(mapConfig.bounds, { maxZoom: mapConfig.maxZoom });
    }
    map.setMinZoom(mapConfig.minZoom);
    map.setMaxZoom(mapConfig.maxZoom);
    // 可选：如果需要重置中心点
    // map.setView(center, map.getZoom());
  }, [mapConfig, map]);

  return null;
};

function App() {
  const position: LatLngTuple = [0, 115];

  const [compositeName, setCompositeName] =
    useState<CompositeType>("ir_clouds");
  const [selectedTime, setSelectedTime] = useState<dayjs.Dayjs>(dayjs());

  const [settingVisible, setSettingVisible] = useState(false);

  const [mapConfig, setMapConfig] = useState<MapConfig>({
    bounds: null,
    minZoom: 0,
    maxZoom: 18,
    tileUrl: "",
    attribution: "",
  });

  const handleSettingClick = () => {
    setSettingVisible((prev) => !prev);
  };

  const handleCompositeChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setCompositeName(event.target.value as CompositeType);
  };

  // Format time to ISO 8601 string for tile URL
  const formatTimeForTileUrl = (time: dayjs.Dayjs): string => {
    return time.format("YYYY-MM-DDTHH:mm:00");
  };

  // Generate tile URL with time parameter
  const generateTileUrl = (baseUrl: string, time: dayjs.Dayjs): string => {
    // Replace {time} placeholder with actual ISO 8601 time
    const timeStr = formatTimeForTileUrl(time);
    return baseUrl.replace("{time}", timeStr);
  };

  useEffect(() => {
    const controller = new AbortController();

    const fetchTileJson = async () => {
      try {
        const tileJson = await ky
          .get(`http://127.0.0.1:5000/${compositeName}.tilejson`, {
            signal: controller.signal,
          })
          .json<TileJSON>();

        // Get the appropriate tile URL template
        // Use the time-based URL (index 1) if available, otherwise use the standard URL (index 0)
        const tileUrlTemplate =
          tileJson.tiles.length > 1 ? tileJson.tiles[1] : tileJson.tiles[0];

        // Generate the actual URL with the selected time
        const tileUrl = generateTileUrl(tileUrlTemplate, selectedTime);

        setMapConfig({
          bounds: tileJson.bounds
            ? [
                [tileJson.bounds[1], tileJson.bounds[0]], // Southwest corner
                [tileJson.bounds[3], tileJson.bounds[2]], // Northeast corner
              ]
            : null,
          minZoom: tileJson.minzoom ?? 0,
          maxZoom: tileJson.maxzoom ?? 18,
          tileUrl: tileUrl,
          attribution: tileJson.attribution ?? "",
        });
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        console.error("Failed to fetch TileJSON:", err);
      }
    };

    fetchTileJson();

    return () => controller.abort();
  }, [compositeName, selectedTime]); // Add selectedTime as a dependency

  // Log when selected time changes
  useEffect(() => {
    console.log(
      `Selected time changed to: ${selectedTime.format("YYYY-MM-DD HH:mm")}`
    );
  }, [selectedTime]);

  const MapDebugger = () => {
    const map = useMap();

    useEffect(() => {
      const logBounds = () => {
        console.log(
          "Current bounds:",
          map.getBounds().getSouthWest(), // 西南角
          map.getBounds().getNorthEast() // 东北角
        );
      };

      map.on("moveend", logBounds);
      return () => {
        map.off("moveend", logBounds);
      };
    }, [map]);

    return null;
  };

  return (
    <>
      <MapContainer
        center={position}
        maxBoundsViscosity={1.0}
        zoom={6}
        minZoom={mapConfig.minZoom}
        maxZoom={mapConfig.maxZoom}
        maxBounds={mapConfig.bounds ?? undefined}
        crs={CRS.EPSG3857}
        keyboard={false}
      >
        <MapDebugger />
        <MapConfigUpdater mapConfig={mapConfig} />
        {mapConfig.tileUrl && (
          <TileLayer
            key={`${compositeName}-${selectedTime.format("YYYY-MM-DDTHH:mm")}`} // Add key to force re-render when time changes
            tileSize={256}
            url={mapConfig.tileUrl}
            minZoom={mapConfig.minZoom}
            maxZoom={mapConfig.maxZoom}
            bounds={mapConfig.bounds ?? undefined}
            attribution={mapConfig.attribution}
            noWrap={true}
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
        <GeoJSON
          data={firs as GeoJSON.GeoJsonObject}
          style={{
            color: "#c8c8c8",
            weight: 2,
            opacity: 1,
            fillOpacity: 0,
          }}
        />
        <Control position="topright">
          <div className="leaflet-control-layers leaflet-control-layers-expanded">
            <label>
              <input
                type="radio"
                name="ir_clouds"
                className="leaflet-control-layers-selector"
                value="ir_clouds"
                checked={compositeName === "ir_clouds"}
                onChange={handleCompositeChange}
              />
              Himawari IR Clouds
            </label>
            <label>
              <input
                type="radio"
                name="true_color"
                className="leaflet-control-layers-selector"
                value="true_color"
                checked={compositeName === "true_color"}
                onChange={handleCompositeChange}
              />
              Himawari True Color
            </label>
          </div>
        </Control>
        <Control position="topleft">
          <button
            className="leaflet-bar leaflet-icon-button"
            onClick={handleSettingClick}
          >
            Pref
          </button>
        </Control>
        <Control position="bottomleft">
          <MousePosition />
        </Control>
        <Control position="bottomright">
          <div className="text-stroke">
            {selectedTime.format("YYYY-MM-DD HH:mm")}
          </div>
        </Control>
      </MapContainer>
      <SettingModal visible={settingVisible} handleClose={handleSettingClick} />
      <TimeRangeSelector onTimeChange={(time) => setSelectedTime(time)} />
    </>
  );
}

export default App;
