/**
 * API Client Utility
 * Handles API requests using ky HTTP client
 */
import ky from "ky";
import type { TileJSON } from "./types";

// Get API configuration from localStorage
export function getApiConfig() {
  return {
    endpoint: localStorage.getItem("endpoint") || "",
    token: localStorage.getItem("token") || "",
  };
}

// Set API configuration to localStorage
export function setApiConfig(config: { endpoint: string; token: string }) {
  localStorage.setItem("endpoint", config.endpoint);
  localStorage.setItem("token", config.token);
}

// Create a ky instance with default options
const createApiClient = () => {
  const { endpoint, token } = getApiConfig();

  return ky.create({
    prefixUrl: endpoint,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    retry: 1,
    timeout: 30000,
  });
};

/**
 * Fetches the latest available timestamps for each composite type
 *
 * @returns A Promise resolving to a Record where:
 *   - Keys are composite names (e.g., 'true_color', 'ir_clouds', 'ash')
 *   - Values are ISO 8601 timestamp strings (e.g., '2025-04-20T04:00:00')
 *
 * Example response:
 * {
 *   "true_color": "2025-04-20T04:00:00",
 *   "ir_clouds": "2025-04-20T04:00:00",
 *   "ash": "2025-04-20T03:30:00"
 * }
 *
 * This data is used to determine the most recent available imagery for each composite type.
 */
export async function fetchLatestComposites(): Promise<Record<string, string>> {
  try {
    const apiClient = createApiClient();
    const data = await apiClient
      .get("composites/latest")
      .json<Record<string, string>>();
    return data;
  } catch (error) {
    console.error("Error fetching latest composites:", error);
    return {};
  }
}

/**
 * Fetches TileJSON metadata for a specific composite type
 *
 * @param composite - The composite name (e.g., 'true_color', 'ir_clouds', 'ash')
 * @returns A Promise resolving to a TileJSON object or null if the request fails
 *
 * Example TileJSON response:
 * {
 *   "tiles": ["https://example.com/true_color/tiles/{time}/{z}/{x}/{y}.png"],
 *   "bounds": [70.0, 0.0, 150.0, 55.0],  // [minLng, minLat, maxLng, maxLat]
 *   "minzoom": 1,
 *   "maxzoom": 10,
 *   "attribution": "© Himawari Satellite Data"
 * }
 *
 * This data is used to configure the map view with appropriate bounds, zoom levels,
 * and tile URL templates that include time parameters for dynamic tile loading.
 */
export async function fetchTileJSON(
  composite: string
): Promise<TileJSON | null> {
  try {
    const apiClient = createApiClient();
    const data = await apiClient.get(`${composite}.tilejson`).json<TileJSON>();
    return data;
  } catch (error) {
    console.error(`Error fetching TileJSON for ${composite}:`, error);
    return null;
  }
}

/**
 * Create a snapshot image with geographic bounds and coastlines
 *
 * @param params - Snapshot parameters
 * @returns A Promise resolving to snapshot response or null if the request fails
 *
 * Example request:
 * {
 *   "bbox": [100.0, 20.0, 140.0, 50.0],  // [min_lng, min_lat, max_lng, max_lat]
 *   "timestamp": "2025-04-20T04:00:00",
 *   "composite": "true_color",
 *   "zoom": 5
 * }
 *
 * Example response:
 * {
 *   "status": "completed",
 *   "download_url": "https://minio.example.com/snapshots/snapshot_true_color_20250420_0400_z5_a1b2c3d4.png?...",
 *   "filename": "snapshot_true_color_20250420_0400_z5_a1b2c3d4.png"
 * }
 */
export async function createSnapshot(params: {
  bbox: [number, number, number, number];
  timestamp: string;
  composite: string;
}): Promise<{
  status: string;
  download_url?: string;
  filename?: string;
  task_id?: string;
  message?: string;
  estimated_wait_time?: string;
} | null> {
  try {
    const apiClient = createApiClient();
    const data = await apiClient.post("api/snapshots", { json: params }).json<{
      status: string;
      download_url?: string;
      filename?: string;
      task_id?: string;
      message?: string;
      estimated_wait_time?: string;
    }>();
    return data;
  } catch (error) {
    console.error("Failed to create snapshot:", error);
    return null;
  }
}
