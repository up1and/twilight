/**
 * API Client Utility
 * Handles API requests using ky HTTP client
 */
import ky from "ky";
import type { TileJSON } from "./types";

interface Task {
  task_id: string;
  composite: string;
  timestamp: string;
  status: "pending" | "processing" | "completed" | "failed";
  priority: string;
  worker_id?: string;
  created_at: string;
  updated_at: string;
  message?: string;
  duration?: number;
  started?: string;
  ended?: string;
}

interface TasksResponse {
  tasks: Task[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

interface Sync {
  timestamp: string;
  source: string;
  status: "pending" | "running" | "completed" | "failed";
  files: number;
  size: number;
  started: string | null;
  ended: string | null;
  duration: number | null;
  speed: number | null;
  created: string;
}

interface SyncsResponse {
  syncs: Sync[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// Get API configuration from localStorage (token only now)
export function getAuthConfig() {
  return {
    token: localStorage.getItem("token") || ""
  };
}

// Set API configuration to localStorage (token only now)
export function setApiConfig(config: { token: string }) {
  localStorage.setItem("token", config.token);
}

// Create a ky instance with default options
const createApiClient = () => {
  const { token } = getAuthConfig();

  return ky.create({
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    retry: 1,
    timeout: 30000
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
      .get("/api/composites/latest")
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
 *   "tiles": ["https://example.com/tiles/true-color/{time}/{z}/{x}/{y}.png"],
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
    const compositeId = composite.replace(/_/g, "-");
    const apiClient = createApiClient();
    const data = await apiClient
      .get(`/tiles/${compositeId}/tile.json`)
      .json<TileJSON>();
    return data;
  } catch (error) {
    console.error(`Error fetching TileJSON for ${composite}:`, error);
    return null;
  }
}

/**
 * Fetch tasks list with optional filtering and pagination
 *
 * @param page - Page number (default: 1)
 * @param perPage - Items per page (default: 20)
 * @param status - Optional status filter (pending, processing, completed, failed)
 * @param composite - Optional composite filter
 * @param priority - Optional priority filter (low, normal, high)
 * @returns A Promise resolving to tasks list response or null if the request fails
 */
export async function fetchTasks(
  page: number = 1,
  perPage: number = 20,
  status?: string,
  composite?: string,
  priority?: string
): Promise<TasksResponse | null> {
  try {
    const params = new URLSearchParams();
    params.append("page", String(page));
    params.append("per_page", String(perPage));
    if (status) params.append("status", status);
    if (composite) params.append("composite", composite);
    if (priority) params.append("priority", priority);

    const apiClient = createApiClient();
    const data = await apiClient
      .get(`/api/tasks?${params.toString()}`)
      .json<TasksResponse>();
    return data;
  } catch (error) {
    console.error("Error fetching tasks:", error);
    return null;
  }
}

/**
 * Fetch sync records from the API
 *
 * @param page - Page number (default: 1)
 * @param perPage - Items per page (default: 20)
 * @param source - Optional source filter (default: himawari)
 * @param status - Optional status filter (pending, running, completed, failed)
 * @returns A Promise resolving to syncs list response or null if the request fails
 */
export async function fetchSyncs(
  page: number = 1,
  perPage: number = 20,
  source?: string,
  status?: string
): Promise<SyncsResponse | null> {
  try {
    const params = new URLSearchParams();
    params.append("page", String(page));
    params.append("per_page", String(perPage));
    if (source) params.append("source", source);
    if (status) params.append("status", status);

    const apiClient = createApiClient();
    const data = await apiClient
      .get(`/api/syncs?${params.toString()}`)
      .json<SyncsResponse>();
    return data;
  } catch (error) {
    console.error("Error fetching syncs:", error);
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
 *   "timedelta": 100
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
  timedelta?: number; // Optional timedelta in minutes for video generation
}): Promise<{
  status: string;
  download_url?: string;
  filename?: string;
  task_id?: string;
  message?: string;
  frame_count?: number;
  time_range?: {
    start: string;
    end: string;
  };
} | null> {
  try {
    const apiClient = createApiClient();
    const data = await apiClient.post("/api/snapshots", { json: params }).json<{
      status: string;
      download_url?: string;
      filename?: string;
      task_id?: string;
      message?: string;
      frame_count?: number;
      time_range?: {
        start: string;
        end: string;
      };
    }>();
    return data;
  } catch (error) {
    console.error("Failed to create snapshot:", error);
    return null;
  }
}

export async function createTask(params: {
  composite: string;
  timestamp: string;
  priority?: string;
}): Promise<{
  task_id: string;
  status: string;
  created: string;
} | null> {
  try {
    const apiClient = createApiClient();
    const data = await apiClient.post("/api/tasks", { json: params }).json<{
      task_id: string;
      status: string;
      created: string;
    }>();
    return data;
  } catch (error) {
    console.error("Failed to create task:", error);
    return null;
  }
}
