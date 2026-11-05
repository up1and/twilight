import { useState, useEffect } from "react";
import { Camera, Video, Loader2 } from "lucide-react";
import {
  createSnapshot,
  getSnapshotJob,
  apiClient,
  resolveApiUrl
} from "../utils/api-client";
import type { SnapshotResponse } from "../utils/api-client";
import type { CompositeType } from "../utils/types";
import dayjs from "dayjs";
import "./snapshot-button.css";

/**
 * Poll a queued snapshot job until it reaches a terminal status.
 *
 * Renders run as RQ jobs, so the client polls:
 *   interval - how often to ask, in milliseconds
 *   timeout  - give up after this long, in milliseconds
 */
async function waitForSnapshot(
  jobId: string,
  shouldStop: () => boolean,
  interval = 1500,
  timeout = 15 * 60 * 1000
): Promise<SnapshotResponse | null> {
  const deadline = Date.now() + timeout;
  let last: SnapshotResponse | null = null;

  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, interval));
    if (shouldStop()) {
      return last;
    }

    const response = await getSnapshotJob(jobId);
    if (!response) {
      continue;
    }

    last = response;
    if (response.status !== "pending" && response.status !== "running") {
      return response;
    }
  }

  return last;
}

interface SnapshotButtonProps {
  composites: CompositeType[];
  selectedTime: dayjs.Dayjs;
  bbox: [number, number, number, number] | null; // [min_lng, min_lat, max_lng, max_lat]
  zoom: number | null; // Map zoom the bbox was captured at
  timedelta?: number; // Time delta in minutes for video generation
}

export default function SnapshotButton({
  composites,
  selectedTime,
  bbox,
  zoom,
  timedelta
}: SnapshotButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isCtrlPressed, setIsCtrlPressed] = useState(false);
  const [cancelled, setCancelled] = useState(false);

  // Drop any in-flight polling when the button unmounts.
  useEffect(() => {
    return () => setCancelled(true);
  }, []);

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

    if (zoom === null) {
      console.error("Map zoom not available");
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
          zoom: number;
          timedelta?: number;
        } = {
          bbox,
          timestamp: selectedTime.utc().format("YYYY-MM-DDTHH:mm:ssZZ"),
          composite: composite,
          zoom
        };

        // If Ctrl is pressed and timedelta is available, generate video
        if (isCtrlPressed && timedelta && timedelta > 0) {
          params.timedelta = timedelta;
        }

        let response = await createSnapshot(params);

        // Only an unfinished job is worth polling; a failed request never
        // reaches this branch because it returns no job id.
        if (
          response?.job_id &&
          (response.status === "pending" || response.status === "running")
        ) {
          response = await waitForSnapshot(response.job_id, () => cancelled);
        }

        if (
          response &&
          response.status === "completed" &&
          response.download_url
        ) {
          // Trigger download by fetching the image and creating a blob
          try {
            const imageResponse = await apiClient.get(
              resolveApiUrl(response.download_url)
            );
            const blob = await imageResponse.blob();

            // Create object URL and trigger download
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            // The object name is the last path segment of download_url.
            link.download =
              response.download_url.split("/").pop() ||
              (params.timedelta ? "snapshot.mp4" : "snapshot.png");
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
          // No job was queued (missing composite, or the render failed).
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
