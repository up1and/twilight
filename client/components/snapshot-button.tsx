import { useState, useEffect } from "react";
import { createSnapshot } from "../utils/api-client";
import type { CompositeType } from "../utils/types";
import dayjs from "dayjs";
import "./snapshot-button.css";

interface SnapshotButtonProps {
  composites: CompositeType[];
  selectedTime: dayjs.Dayjs;
  bbox: [number, number, number, number] | null; // [min_lng, min_lat, max_lng, max_lat]
  timedelta?: number; // Time delta in minutes for video generation
}

export default function SnapshotButton({
  composites,
  selectedTime,
  bbox,
  timedelta,
}: SnapshotButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isCtrlPressed, setIsCtrlPressed] = useState(false);

  // Track Ctrl key state
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Control") {
        setIsCtrlPressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === "Control") {
        setIsCtrlPressed(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  const handleSnapshot = async () => {
    if (!bbox) {
      console.error("Map bounds not available");
      return;
    }

    setIsLoading(true);

    try {
      // Process each composite
      for (const composite of composites) {
        const params: {
          bbox: [number, number, number, number];
          timestamp: string;
          composite: string;
          timedelta?: number;
        } = {
          bbox,
          timestamp: selectedTime.utc().format("YYYY-MM-DDTHH:mm:ssZZ"),
          composite: composite,
        };

        // If Ctrl is pressed and timedelta is available, generate video
        if (isCtrlPressed && timedelta && timedelta > 0) {
          params.timedelta = timedelta;
        }

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
          console.error(
            "Failed to create snapshot for",
            composite,
            response?.message
          );
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
        ) : isCtrlPressed ? (
          // Video icon
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
            <polygon points="23 7 16 12 23 17 23 7" />
            <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
          </svg>
        ) : (
          // Camera icon
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
