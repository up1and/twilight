import { useEffect, useRef, forwardRef, useCallback } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import dayjs from "dayjs";

const generateTileUrl = (baseUrl: string, time: dayjs.Dayjs): string => {
  const timeStr = time.utc().format("YYYY-MM-DDTHH:mm:ss");
  return baseUrl.replace("{time}", timeStr);
};

class TimeLayerCache {
  private cache: Map<number, L.TileLayer> = new Map();
  private map: L.Map;
  private cacheRangeMinutes: number;

  constructor(map: L.Map, cacheRangeMinutes: number = 60) {
    this.map = map;
    this.cacheRangeMinutes = cacheRangeMinutes;
  }

  has(timestamp: number): boolean {
    return this.cache.has(timestamp);
  }

  get(timestamp: number): L.TileLayer | undefined {
    return this.cache.get(timestamp);
  }

  set(timestamp: number, layer: L.TileLayer): void {
    // Add new layer to cache
    this.cache.set(timestamp, layer);
    // Clean up if cache is too large
    this.cleanup(timestamp);
  }

  delete(timestamp: number): boolean {
    const layer = this.cache.get(timestamp);
    if (layer && this.map.hasLayer(layer)) {
      this.map.removeLayer(layer);
    }
    return this.cache.delete(timestamp);
  }

  // Clean up layers outside the time window
  private cleanup(baseTimestamp: number): void {
    // Calculate max cache size based on time range
    const maxSize = Math.floor(this.cacheRangeMinutes / 10) * 2 + 1;

    // Only clean up if cache exceeds max size
    if (this.cache.size <= maxSize) return;

    const milliseconds = this.cacheRangeMinutes * 60000;
    const minTime = baseTimestamp - milliseconds;
    const maxTime = baseTimestamp + milliseconds;

    // Remove layers outside time window
    this.cache.forEach((_, timestamp) => {
      if (timestamp < minTime || timestamp > maxTime) {
        this.delete(timestamp);
      }
    });
  }

  // Clear cache with option to keep specific layer
  clear(keepLayer: L.TileLayer | null = null): void {
    this.cache.forEach((layer, timestamp) => {
      if (layer !== keepLayer) {
        this.delete(timestamp);
      }
    });
  }

  // Get cache size
  size(): number {
    return this.cache.size;
  }
}

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
  const layerCache = useRef(new TimeLayerCache(map, 60));
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
  };

  // Preload adjacent time layer (current +/- 10 minutes)
  const preloadAdjacentLayer = (currentTime: dayjs.Dayjs) => {
    const timesToPreload = [
      currentTime.add(10, "minute"),
      currentTime.subtract(10, "minute"),
    ];

    timesToPreload.forEach((time) => {
      if (timelineTime && time.isAfter(timelineTime)) return;

      const timestamp = time.valueOf();
      if (!layerCache.current.has(timestamp)) {
        const layer = createTileLayer(time);
        layer.addTo(map);
        layer.setOpacity(0);
        layerCache.current.set(timestamp, layer);
      }
    });
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

    // Preload adjacent layer
    preloadAdjacentLayer(currentTime);
  }, [currentTime, urlTemplate, map, zIndex, updateRef]);

  // Handle view changes
  useEffect(() => {
    if (!map) return;

    const handleViewChange = () => {
      // Clear cache except current layer
      layerCache.current.clear(currentLayerRef.current);
      // Preload after view change
      setTimeout(() => preloadAdjacentLayer(currentTime), 100);
    };

    map.on("zoomend", handleViewChange);
    map.on("moveend", handleViewChange);
    return () => {
      map.off("zoomend", handleViewChange);
      map.off("moveend", handleViewChange);
    };
  }, [map, currentTime]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      layerCache.current.clear();
      updateRef(null);
    };
  }, [map, updateRef]);

  return null;
});

TimeDimensionLayer.displayName = "TimeDimensionLayer";

export default TimeDimensionLayer;
