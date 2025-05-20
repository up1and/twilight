/**
 * API Client Utility
 * Handles API requests using ky HTTP client
 */
import ky from "ky";

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

// Format composite name for display (e.g., "day_convection" to "Day Convection")
export function formatCompositeName(name: string): string {
  // Special case for ir_clouds
  if (name === "ir_clouds") {
    return "IR Clouds";
  }

  // Handle other cases with standard formatting
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
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
