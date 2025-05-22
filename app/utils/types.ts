export type CompositeType =
  | "true_color"
  | "ir_clouds"
  | "ash"
  | "water_vapor"
  | string;

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
