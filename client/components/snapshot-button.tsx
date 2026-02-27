import { useState, useEffect } from "react";
import { Camera, Video, Loader2 } from "lucide-react";
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
  timedelta
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
          composite: composite
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
          <Loader2 size={16} className="loading-icon" />
        ) : isCtrlPressed ? (
          <Video size={16} />
        ) : (
          <Camera size={16} />
        )}
      </button>
    </div>
  );
}
