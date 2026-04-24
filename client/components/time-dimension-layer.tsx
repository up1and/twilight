import {
  useEffect,
  useCallback,
  useImperativeHandle,
  useRef,
  forwardRef
} from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import dayjs from "dayjs";

const generateTileUrl = (baseUrl: string, time: dayjs.Dayjs): string => {
  const timeStr = time.utc().format("YYYY-MM-DDTHH-mm-ss[Z]");
  return baseUrl.replace("{time}", timeStr);
};

interface CachedLayer {
  layer: L.TileLayer;
  status: "loading" | "loaded" | "error";
}

class TimeLayerCache {
  private cache: Map<number, CachedLayer> = new Map();
  private map: L.Map;
  private cacheRangeMinutes: number;

  constructor(map: L.Map, cacheRangeMinutes: number = 60) {
    this.map = map;
    this.cacheRangeMinutes = cacheRangeMinutes;
  }

  has(timestamp: number): boolean {
    return this.cache.has(timestamp);
  }

  get(timestamp: number): CachedLayer | undefined {
    return this.cache.get(timestamp);
  }

  set(timestamp: number, layer: L.TileLayer): void {
    // Add new layer to cache
    this.cache.set(timestamp, { layer, status: "loading" });
    // Clean up if cache is too large
    this.cleanup(timestamp);
  }

  setStatus(timestamp: number, status: "loading" | "loaded" | "error"): void {
    const state = this.cache.get(timestamp);
    if (state) {
      state.status = status;
    }
  }

  delete(timestamp: number): boolean {
    const state = this.cache.get(timestamp);
    if (state && this.map.hasLayer(state.layer)) {
      this.map.removeLayer(state.layer);
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
    this.cache.forEach((state, timestamp) => {
      if (state.layer !== keepLayer) {
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
  onBufferingChange?: (isBuffering: boolean) => void;
  attribution?: string;
}

export interface TimeDimensionLayerHandles {
  getCurrentLayer: () => L.TileLayer | null;
  getCachedLayers: () => L.TileLayer[];
}

const TimeDimensionLayer = forwardRef<
  TimeDimensionLayerHandles,
  TimeDimensionLayerProps
>(
  (
    { urlTemplate, currentTime, timelineTime, bounds, onBufferingChange, attribution },
    ref
  ) => {
    const zIndex = 100;
    const map = useMap();
    const isBufferingRef = useRef<boolean>(false);

    // Cache system using Map<timestamp, TileLayer>
    const layerCache = useRef(new TimeLayerCache(map, 60));
    const currentLayerRef = useRef<L.TileLayer | null>(null);

    // Expose handle
    useImperativeHandle(
      ref,
      () => ({
        getCurrentLayer: () => currentLayerRef.current,
        getCachedLayers: () => {
          const layers: L.TileLayer[] = [];
          layerCache.current["cache"].forEach((state) => {
            layers.push(state.layer);
          });
          return layers;
        }
      }),
      []
    );

    // Update buffering state helper
    const updateBufferingState = useCallback(
      (isBuffering: boolean) => {
        if (isBufferingRef.current !== isBuffering) {
          isBufferingRef.current = isBuffering;
          onBufferingChange?.(isBuffering);
        }
      },
      [onBufferingChange]
    );

    // Check if next layer is ready (loaded or error)
    const checkNextLayer = useCallback(
      (targetTime: dayjs.Dayjs) => {
        const nextTime = targetTime.add(10, "minute");

        // If next time is after timeline, consider it ready
        if (timelineTime && nextTime.isAfter(timelineTime)) return true;

        const timestamp = nextTime.valueOf();
        const state = layerCache.current.get(timestamp);
        // If layer doesn't exist yet, consider it ready (not preloaded)
        if (!state) return true;
        return state.status === "loaded" || state.status === "error";
      },
      [timelineTime]
    );

    // Create tile layer
    const createTileLayer = (targetTime: dayjs.Dayjs): L.TileLayer => {
      const url = generateTileUrl(urlTemplate, targetTime);
      const timestamp = targetTime.valueOf();

      const layer = L.tileLayer(url, {
        zIndex: zIndex - 1,
        opacity: 0,
        className: "time-dimension-layer",
        noWrap: true,
        bounds,
        attribution
      });

      // Track layer state
      layer.on("loading", () => {
        updateBufferingState(true);
      });

      layer.on("load", () => {
        layerCache.current.setStatus(timestamp, "loaded");
        if (checkNextLayer(targetTime)) {
          updateBufferingState(false);
        }
      });

      layer.on("tileerror", () => {
        // Mark error to stop buffering for this timestamp
        layerCache.current.setStatus(timestamp, "error");
        if (checkNextLayer(targetTime)) {
          updateBufferingState(false);
        }
      });

      return layer;
    };

    // Layer switching logic
    const switchToTime = (targetTime: dayjs.Dayjs) => {
      const timestamp = targetTime.valueOf();
      const currentLayer = currentLayerRef.current;

      // Get or create target layer
      let targetLayer: L.TileLayer;
      const cachedLayer = layerCache.current.get(timestamp);
      if (cachedLayer) {
        targetLayer = cachedLayer.layer;
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

      // Check if we can stop buffering after switching
      if (checkNextLayer(targetTime)) {
        updateBufferingState(false);
      }
    };

    // Preload adjacent time layer (current +/- 10 minutes)
    const preloadAdjacentLayer = (currentTime: dayjs.Dayjs) => {
      const timesToPreload = [
        currentTime.add(10, "minute"),
        currentTime.subtract(10, "minute")
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
      } else {
        switchToTime(currentTime);
      }

      // Preload adjacent layer
      preloadAdjacentLayer(currentTime);
    }, [currentTime, urlTemplate, map]);

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
        currentLayerRef.current = null;
      };
    }, [map]);

    return null;
  }
);

TimeDimensionLayer.displayName = "TimeDimensionLayer";

export default TimeDimensionLayer as React.ForwardRefExoticComponent<
  TimeDimensionLayerProps & React.RefAttributes<TimeDimensionLayerHandles>
> & {
  displayName?: string;
};
