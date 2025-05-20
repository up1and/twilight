import dayjs from "dayjs";

export type CompositeType =
  | "true_color"
  | "ir_clouds"
  | "ash"
  | "water_vapor"
  | string;

export interface ImageType {
  datetime: dayjs.Dayjs;
  key: string;
  url?: string;
}

export interface CompositeListType {
  true_color: Array<ImageType>;
  ir_clouds: Array<ImageType>;
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
