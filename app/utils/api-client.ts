/**
 * API Client Utility
 * Handles API requests, automatically retrieving endpoint and token from localStorage
 */

// Get API configuration
export function getApiConfig() {
  return {
    endpoint: localStorage.getItem("endpoint") || "https://example.com/api",
    token: localStorage.getItem("token") || "",
  };
}

// Set API configuration
export function setApiConfig(config: { endpoint: string; token: string }) {
  localStorage.setItem("endpoint", config.endpoint);
  localStorage.setItem("token", config.token);
}

// Example API request function
export async function fetchData(path: string, options: RequestInit = {}) {
  const { endpoint, token } = getApiConfig();

  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${endpoint}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json();
}

// Additional API methods can be added here
// For example: fetchTileData, fetchCompositeList, etc.
