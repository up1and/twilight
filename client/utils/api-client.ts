/**
 * API Client Utility
 * Handles API requests using ky HTTP client
 */
import ky from "ky";
import type { TileJSON, Task, Sync, Profile, CompositeInfo } from "./types";
import { storage } from "./storage";

interface TasksResponse {
  tasks: Task[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

interface SyncsResponse {
  syncs: Sync[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// Get auth token from localStorage
function getAuthToken(): string {
  return storage.get("auth-token") || "";
}

// Verify token with backend
export async function verifyToken(token: string): Promise<boolean> {
  try {
    const response = await apiClient.post(apiUrl("/api/auth/verify"), {
      json: { token }
    });
    const data = (await response.json()) as { valid: boolean };
    return data.valid;
  } catch (error) {
    console.error("Error verifying token:", error);
    return false;
  }
}

// API base URL
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export function resolveApiUrl(path: string): string {
  if (!API_BASE || /^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_BASE.replace(/\/+$/, "")}${path}`;
}

// Create a ky instance with default options and dynamic auth token
export const apiClient = ky.create({
  headers: {
    "Content-Type": "application/json"
  },
  retry: 1,
  timeout: 30000,
  hooks: {
    beforeRequest: [
      (request) => {
        const token = getAuthToken();
        if (token) {
          request.headers.set("Authorization", `Bearer ${token}`);
        }
      }
    ]
  }
});

/**
 * Fetches composite metadata — latest timestamp and availability for each composite type.
 *
 * @returns A Promise resolving to a Record where:
 *   - Keys are composite names (e.g., 'true_color', 'ir_clouds', 'ash')
 *   - Values are CompositeInfo objects with `timestamp` and `availability`
 *
 * Example response:
 * {
 *   "true_color": { "timestamp": "2025-04-20T04:00:00", "availability": "day" },
 *   "ir_clouds": { "timestamp": "2025-04-20T04:00:00", "availability": "all" },
 *   "ash": { "timestamp": "2025-04-20T03:30:00", "availability": "all" }
 * }
 */
export async function fetchComposites(): Promise<
  Record<string, CompositeInfo>
> {
  try {
    const data = await apiClient
      .get(apiUrl("/api/composites"))
      .json<Record<string, CompositeInfo>>();
    return data;
  } catch (error) {
    console.error("Error fetching composites:", error);
    return {};
  }
}

/**
 * Fetch legend data for a specific composite type
 *
 * @param composite - The composite name (e.g., 'true_color', 'ir_clouds', 'ash')
 * @returns A Promise resolving to an array of legend items or null if the request fails
 *
 * Example response:
 * [
 *   { "colors": ["#FF6B6B"], "label": "Ash" },
 *   { "colors": ["#43ff89", "#eae98f"], "label": "Ash (mixed SO2)" }
 * ]
 */
export async function fetchLegend(
  composite: string
): Promise<{ colors: string[]; label: string }[] | null> {
  try {
    const compositeId = composite.replace(/_/g, "-");
    const data = await apiClient
      .get(apiUrl(`/tiles/${compositeId}/legend.json`))
      .json<{ colors: string[]; label: string }[]>();
    return data;
  } catch (error) {
    console.error(`Error fetching legend for ${composite}:`, error);
    return null;
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

    const data = await apiClient
      .get(apiUrl(`/tiles/${compositeId}/tile.json`))
      .json<TileJSON>();
    return {
      ...data,
      tiles: data.tiles?.map(resolveApiUrl) ?? []
    };
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

    const data = await apiClient
      .get(apiUrl(`/api/tasks?${params.toString()}`))
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

    const data = await apiClient
      .get(apiUrl(`/api/syncs?${params.toString()}`))
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
    const data = await apiClient
      .post(apiUrl("/api/snapshots"), { json: params })
      .json<{
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
    const data = await apiClient
      .post(apiUrl("/api/tasks"), { json: params })
      .json<{
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

/**
 * Fetch profile data for a specific task
 *
 * @param taskId - The task ID to fetch profile for
 * @returns A Promise resolving to Profile data or null if not found
 */
export async function fetchProfile(taskId: string): Promise<Profile | null> {
  try {
    const data = await apiClient
      .get(apiUrl(`/api/tasks/${taskId}/profile`))
      .json<Profile>();
    return data;
  } catch (error) {
    console.error("Error fetching profile:", error);
    return null;
  }
}
