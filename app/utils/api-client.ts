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

// Fetch latest composites
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

// Fetch TileJSON data for a composite
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
