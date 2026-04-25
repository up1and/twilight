export type CompositeType =
  | "airmass"
  | "ash"
  | "cloud_phase"
  | "cloudtop"
  | "convection"
  | "day_microphysics"
  | "dust"
  | "fire_temperature"
  | "fog"
  | "geo_color"
  | "ir_clouds"
  | "natural_color"
  | "night_microphysics"
  | "overview"
  | "true_color"
  | "water_vapor";

export interface MapLayers {
  "fir-boundary": boolean;
}

export interface TileJSON {
  tiles: string[];
  bounds?: [number, number, number, number]; // [minLng, minLat, maxLng, maxLat]
  minzoom?: number;
  maxzoom?: number;
  attribution?: string;
}

export interface MapConfig {
  bounds: L.LatLngBoundsExpression | null;
  minZoom: number;
  maxZoom: number;
  tileUrl: string;
  attribution: string;
}

export interface Task {
  task_id: string;
  composite: string;
  timestamp: string;
  status: "pending" | "processing" | "completed" | "failed";
  priority: string;
  worker_id?: string;
  created: string;
  message?: string;
  duration?: number;
  started?: string;
  ended?: string;
}

export interface Sync {
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

export interface ProfileTask {
  key: string;
  duration: number;
}

export interface ProfileResource {
  time: number;
  memory: number;
  cpu_percent: number;
}

export interface Profile {
  task_id: string;
  tasks: ProfileTask[];
  resources: ProfileResource[];
}
