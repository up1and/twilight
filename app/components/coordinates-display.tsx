import "./coordinates-display.css";

interface CoordinatesDisplayProps {
  lat: number;
  lng: number;
}

export default function CoordinatesDisplay({
  lat,
  lng,
}: CoordinatesDisplayProps) {
  // Convert decimal degrees to degrees, minutes, seconds format
  const formatToDMS = (coordinate: number, isLatitude: boolean) => {
    const absolute = Math.abs(coordinate);
    const degrees = Math.floor(absolute);
    const minutesNotTruncated = (absolute - degrees) * 60;
    const minutes = Math.floor(minutesNotTruncated);
    const seconds = Math.floor((minutesNotTruncated - minutes) * 60);

    const direction = isLatitude
      ? coordinate >= 0
        ? "N"
        : "S"
      : coordinate >= 0
      ? "E"
      : "W";

    return `${degrees}°${minutes}'${seconds}" ${direction}`;
  };

  return (
    <div className="coordinates-display">
      <div className="coordinates-text">
        {formatToDMS(lat, true)} | {formatToDMS(lng, false)}
      </div>
    </div>
  );
}
