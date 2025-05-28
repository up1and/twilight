import { useState } from "react";
import { createSnapshot } from "../utils/api-client";
import type { CompositeType } from "../utils/types";
import dayjs from "dayjs";
import "./snapshot-button.css";

interface SnapshotButtonProps {
  composites: CompositeType[];
  selectedTime: dayjs.Dayjs;
  mapRef: React.MutableRefObject<L.Map | null>;
}

export default function SnapshotButton({
  composites,
  selectedTime,
  mapRef,
}: SnapshotButtonProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleSnapshot = async () => {
    if (!mapRef.current) {
      console.error("Map not available");
      return;
    }

    // Get current map bounds
    const mapBounds = mapRef.current.getBounds();
    setIsLoading(true);

    try {
      // Convert Leaflet bounds to bbox array [min_lng, min_lat, max_lng, max_lat]
      const bbox: [number, number, number, number] = [
        mapBounds.getWest(),
        mapBounds.getSouth(),
        mapBounds.getEast(),
        mapBounds.getNorth(),
      ];

      // Process each composite
      for (const composite of composites) {
        const params = {
          bbox,
          timestamp: selectedTime.utc().format("YYYY-MM-DDTHH:mm:ss"),
          composite: composite,
        };

        const response = await createSnapshot(params);

        if (
          response &&
          response.status === "completed" &&
          response.download_url
        ) {
          // Trigger download by fetching the image and creating a blob
          try {
            const imageResponse = await fetch(response.download_url);
            const blob = await imageResponse.blob();

            // Create object URL and trigger download
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = response.filename || "snapshot.png";
            link.style.display = "none";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // Clean up object URL
            window.URL.revokeObjectURL(url);
          } catch (downloadError) {
            console.error("Download error:", downloadError);
          }
        } else {
          console.error("Failed to create snapshot for", composite);
        }
      }
    } catch (error) {
      console.error("Snapshot error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="snapshot-button-container">
      <button
        className="snapshot-button"
        onClick={handleSnapshot}
        disabled={isLoading}
        title="Snapshot"
      >
        {isLoading ? (
          <svg
            className="loading-icon"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 12a9 9 0 11-6.219-8.56" />
          </svg>
        ) : (
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="13" r="4" />
          </svg>
        )}
      </button>
    </div>
  );
}
