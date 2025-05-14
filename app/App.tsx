import { useState, useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  useMapEvent,
  useMap,
} from "react-leaflet";
import { LatLngTuple, CRS } from "leaflet";
import ky from "ky";

import Control from "./components/Control";
import SettingModal from "./components/Setting";
import {
  CompositeListType,
  CompositeType,
  ImageType,
  MapConfig,
  TileJSON,
} from "./utils/types";
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
  const maxBounds: [LatLngTuple, LatLngTuple] = [
    [0, 70], // south west
    [55, 150], // north east
  ];

  const [image, setImage] = useState<ImageType>();
  const [compositeName, setCompositeName] =
    useState<CompositeType>("ir_clouds");
  const [composites] = useState<CompositeListType>({
    ir_clouds: [],
    true_color: [],
  });
  const [playing, setPlaying] = useState<boolean>(false);
  const [, setCurrentIndex] = useState<number>(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [settingVisible, setSettingVisible] = useState(false);

  const [mapConfig, setMapConfig] = useState<MapConfig>({
    bounds: null,
    minZoom: 0,
    maxZoom: 18,
    tileUrl: "",
    attribution: "",
  });

  const handlePlayClick = () => {
    setPlaying((prev) => !prev);
    console.log("play", playing);
  };

  const handleSettingClick = () => {
    setSettingVisible((prev) => !prev);
  };

  const handleCompositeChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setCompositeName(event.target.value as CompositeType);
  };

  const fetchImage = async (object: ImageType) => {
    const url = "";
    const currentImage: ImageType = {
      datetime: object.datetime,
      key: object.key,
      url: url,
    };
    setImage(currentImage);
  };

  useEffect(() => {
    const controller = new AbortController();

    const fetchTileJson = async () => {
      try {
        const tileJson = await ky
          .get(`http://127.0.0.1:5000/${compositeName}/tilejson.json`, {
            signal: controller.signal,
          })
          .json<TileJSON>();
        setMapConfig({
          bounds: tileJson.bounds
            ? [
                [tileJson.bounds[1], tileJson.bounds[0]], // 西南角
                [tileJson.bounds[3], tileJson.bounds[2]], // 东北角
              ]
            : null,
          minZoom: tileJson.minzoom ?? 0,
          maxZoom: tileJson.maxzoom ?? 18,
          tileUrl: tileJson.tiles[0],
          attribution: tileJson.attribution ?? "",
        });
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        console.error("Failed to fetch TileJSON:", err);
      }
    };

    fetchTileJson();

    return () => controller.abort();
  }, [compositeName]);

  useEffect(() => {
    const fetchComposites = async () => {
      console.log("update objects");
    };

    fetchComposites();
    const intervalId = setInterval(fetchComposites, 60000);

    return () => clearInterval(intervalId);
  }, []);

  useEffect(() => {
    let images = composites[compositeName];

    if (playing) {
      intervalRef.current = setInterval(() => {
        setCurrentIndex((prevIndex) => {
          const nextIndex = (prevIndex + 1) % images.length;
          const currentImage = images[nextIndex];
          fetchImage(currentImage);
          return nextIndex;
        });
      }, 200);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    } else {
      if (images.length > 0) {
        const latestObject = images[images.length - 1];
        fetchImage(latestObject);
        setCurrentIndex(0);
      }
    }
  }, [playing, composites, compositeName]);

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
    <MapContainer
      center={position}
      maxBoundsViscosity={1.0}
      zoom={6}
      minZoom={mapConfig.minZoom}
      maxZoom={mapConfig.maxZoom}
      maxBounds={mapConfig.bounds ?? undefined}
      crs={CRS.EPSG3857}
    >
      <MapDebugger />
      <MapConfigUpdater mapConfig={mapConfig} />
      {mapConfig.tileUrl && (
        <TileLayer
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
          onClick={handlePlayClick}
        >
          {playing ? "Stop" : "Play"}
        </button>
        <br />
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
        {image && (
          <div className="text-stroke">
            {image.datetime.format("YYYY-MM-DD HH:mm")}
          </div>
        )}
      </Control>
      <SettingModal visible={settingVisible} handleClose={handleSettingClick} />
    </MapContainer>
  );
}

export default App;
