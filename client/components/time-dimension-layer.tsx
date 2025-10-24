import { useEffect, useRef, forwardRef, useCallback } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import dayjs from "dayjs";

const generateTileUrl = (baseUrl: string, time: dayjs.Dayjs): string => {
  const timeStr = time.utc().format("YYYY-MM-DDTHH:mm:ss");
  return baseUrl.replace("{time}", timeStr);
};

interface TimeDimensionLayerProps {
  urlTemplate: string;
  currentTime: dayjs.Dayjs;
  timelineTime?: dayjs.Dayjs;
  bounds?: L.LatLngBoundsExpression;
  zIndex?: number;
}

const TimeDimensionLayer = forwardRef<
  L.TileLayer | null,
  TimeDimensionLayerProps
>(({ urlTemplate, currentTime, timelineTime, bounds, zIndex = 100 }, ref) => {
  const map = useMap();

  // Cache system using Map<timestamp, TileLayer>
  const layerCache = useRef<Map<number, L.TileLayer>>(new Map());
  const currentLayerRef = useRef<L.TileLayer | null>(null);

  // Update ref helper
  const updateRef = useCallback(
    (layer: L.TileLayer | null) => {
      if (typeof ref === "function") {
        ref(layer);
      } else if (ref) {
        ref.current = layer;
      }
    },
    [ref]
  );

  // Create tile layer
  const createTileLayer = (targetTime: dayjs.Dayjs): L.TileLayer => {
    const url = generateTileUrl(urlTemplate, targetTime);

    return L.tileLayer(url, {
      zIndex: zIndex - 1,
      opacity: 0,
      className: "time-dimension-layer",
      noWrap: true,
      bounds,
    });
  };

  // Layer switching logic
  const switchToTime = (targetTime: dayjs.Dayjs) => {
    const timestamp = targetTime.valueOf();
    const currentLayer = currentLayerRef.current;

    // Get or create target layer
    let targetLayer: L.TileLayer;
    if (layerCache.current.has(timestamp)) {
      targetLayer = layerCache.current.get(timestamp)!;
    } else {
      targetLayer = createTileLayer(targetTime);
      layerCache.current.set(timestamp, targetLayer);
      targetLayer.addTo(map);
    }

    // Instant switch
    if (currentLayer) {
      currentLayer.setOpacity(0);
      currentLayer.setZIndex(zIndex - 1);
    }

    // Update current layer reference
    targetLayer.setOpacity(1);
    targetLayer.setZIndex(zIndex);
    currentLayerRef.current = targetLayer;
    updateRef(targetLayer);

    // Cleanup if cache is too large
    if (layerCache.current.size > 36) {
      const oldestLayer = layerCache.current.keys().next();
      if (!oldestLayer.done) {
        layerCache.current.delete(oldestLayer.value);
      }
    }
  };

  // Preload only next time layer (current + 10 minutes)
  const preloadNextLayer = (currentTime: dayjs.Dayjs) => {
    const nextTime = currentTime.add(10, "minute");
    if (timelineTime && nextTime.isAfter(timelineTime)) {
      return;
    }

    const timestamp = nextTime.valueOf();
    if (!layerCache.current.has(timestamp)) {
      const layer = createTileLayer(nextTime);
      layer.addTo(map);
      layer.setOpacity(0);
      layerCache.current.set(timestamp, layer);
    }
  };

  // Main effect - handles time changes
  useEffect(() => {
    if (!map || !urlTemplate) return;

    const timestamp = currentTime.valueOf();

    // Initial setup
    if (!currentLayerRef.current) {
      const initialLayer = createTileLayer(currentTime);
      layerCache.current.set(timestamp, initialLayer);
      initialLayer.addTo(map);
      initialLayer.setOpacity(1);
      initialLayer.setZIndex(zIndex);
      currentLayerRef.current = initialLayer;
      updateRef(initialLayer);
    } else {
      switchToTime(currentTime);
    }

    // Preload next layer
    preloadNextLayer(currentTime);
  }, [currentTime, urlTemplate, map, zIndex, updateRef]);

  // Handle zoom changes
  useEffect(() => {
    if (!map) return;

    const handleZoomEnd = () => {
      // Clear cache except current layer
      layerCache.current.forEach((layer, timestamp) => {
        if (layer !== currentLayerRef.current) {
          map.removeLayer(layer);
          layerCache.current.delete(timestamp);
        }
      });

      // Preload after zoom
      setTimeout(() => preloadNextLayer(currentTime), 100);
    };

    map.on("zoomend", handleZoomEnd);
    return () => {
      map.off("zoomend", handleZoomEnd);
    };
  }, [map, currentTime]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      layerCache.current.forEach((layer) => {
        if (map.hasLayer(layer)) map.removeLayer(layer);
      });
      layerCache.current.clear();
      updateRef(null);
    };
  }, [map, updateRef]);

  return null;
});

export default TimeDimensionLayer;
