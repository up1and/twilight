import type React from "react";
import { useEffect, useRef, useState } from "react";
import dayjs from "dayjs";
import "./time-range-selector.css";

interface TimeRangeSelectorProps {
  initialTime?: Date | dayjs.Dayjs | string;
  onTimeChange?: (time: dayjs.Dayjs) => void;
}

export default function TimeRangeSelector({
  initialTime = dayjs(),
  onTimeChange,
}: TimeRangeSelectorProps) {
  // Initialize time, ensuring minutes are rounded to the nearest 10
  const roundToNearestTenMinutes = (
    date: dayjs.Dayjs | Date | string
  ): dayjs.Dayjs => {
    const dayjsDate = dayjs(date);
    const minutes = dayjsDate.minute();
    const roundedMinutes = Math.round(minutes / 10) * 10;
    return dayjsDate.minute(roundedMinutes).second(0).millisecond(0);
  };

  const [currentTime, setCurrentTime] = useState<dayjs.Dayjs>(
    roundToNearestTenMinutes(new Date())
  );
  const [selectedTime, setSelectedTime] = useState<dayjs.Dayjs>(
    roundToNearestTenMinutes(initialTime)
  );
  const [lookbackHours, setLookbackHours] = useState<number>(3); // Default to 3 hours lookback
  const [isDraggingMarker, setIsDraggingMarker] = useState<boolean>(false);
  const [isDraggingTimeline, setIsDraggingTimeline] = useState<boolean>(false);
  const [dragStartX, setDragStartX] = useState<number>(0);
  const [dragStartTime, setDragStartTime] = useState<dayjs.Dayjs | null>(null);
  const [dragStartSelectedTime, setDragStartSelectedTime] =
    useState<dayjs.Dayjs | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [recentlyDragged, setRecentlyDragged] = useState<boolean>(false);
  const [hasMoved, setHasMoved] = useState<boolean>(false); // Track if mouse has moved during drag
  const timelineRef = useRef<HTMLDivElement>(null);
  const markerRef = useRef<HTMLDivElement>(null);
  const [timeIntervals, setTimeIntervals] = useState<any[]>([]);

  // Format time as HH:MM
  const formatTime = (date: dayjs.Dayjs): string => {
    return date.format("HH:mm");
  };

  // Format full date and time as YYYY-MM-DD HH:MM
  const formatFullDateTime = (date: dayjs.Dayjs): string => {
    return date.format("YYYY-MM-DD HH:mm");
  };

  // Format date for datetime-local input
  const formatDateTimeInput = (date: dayjs.Dayjs): string => {
    return date.format("YYYY-MM-DDTHH:mm");
  };

  // Parse datetime-local input value
  const parseDateTimeInput = (value: string): dayjs.Dayjs => {
    return dayjs(value);
  };

  // Calculate start time based on current time and lookback hours
  const getStartTime = (): dayjs.Dayjs => {
    return currentTime.subtract(lookbackHours, "hour");
  };

  // Calculate end time (always current time)
  const getEndTime = (): dayjs.Dayjs => {
    return currentTime;
  };

  // Generate time intervals for the timeline
  const generateTimeIntervals = () => {
    const intervals = [];
    const startTime = getStartTime();
    const endTime = getEndTime();

    // Calculate how many 10-minute intervals we need
    const totalMinutes = lookbackHours * 60;
    const totalIntervals = totalMinutes / 10;

    for (let i = 0; i <= totalIntervals; i++) {
      const time = startTime.add(i * 10, "minute");

      // Don't go beyond the end time
      if (time.isAfter(endTime)) break;

      intervals.push({
        time: time,
        label: formatTime(time),
        isHour: time.minute() === 0,
        isHalfHour: time.minute() === 30,
      });
    }

    return intervals;
  };

  // Update time intervals when lookback hours or current time changes
  useEffect(() => {
    const newIntervals = generateTimeIntervals();
    setTimeIntervals(newIntervals);

    // Ensure selected time is within the new range
    const startTime = getStartTime();
    const endTime = getEndTime();

    if (selectedTime.isBefore(startTime)) {
      updateSelectedTime(startTime);
    } else if (selectedTime.isAfter(endTime)) {
      updateSelectedTime(endTime);
    }
  }, [lookbackHours, currentTime]);

  // Update selected time and ensure it's rounded to nearest 10 minutes
  const updateSelectedTime = (newTime: dayjs.Dayjs) => {
    const roundedTime = roundToNearestTenMinutes(newTime);
    setSelectedTime(roundedTime);
    onTimeChange?.(roundedTime);
  };

  // Handle timeline click
  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // Don't handle click if we were dragging or recently finished dragging with movement
    if (isDraggingTimeline || (recentlyDragged && hasMoved)) return;

    if (!timelineRef.current || timeIntervals.length === 0) return;

    const rect = timelineRef.current.getBoundingClientRect();
    const clickPosition = e.clientX - rect.left;
    const percentage = clickPosition / rect.width;

    // Find the closest time interval
    const index = Math.min(
      Math.floor(percentage * timeIntervals.length),
      timeIntervals.length - 1
    );

    // Use the exact time from the interval
    updateSelectedTime(timeIntervals[index].time);
  };

  // Handle marker drag start
  const handleMarkerDragStart = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation(); // Prevent timeline drag
    setIsDraggingMarker(true);
    // Pause playback if dragging
    if (isPlaying) {
      setIsPlaying(false);
    }
  };

  // Handle timeline drag start
  const handleTimelineDragStart = (e: React.MouseEvent<HTMLDivElement>) => {
    // Only start timeline drag if we're not dragging the marker
    if (isDraggingMarker) return;

    e.preventDefault();
    setIsDraggingTimeline(true);
    setDragStartX(e.clientX);
    setDragStartTime(currentTime);
    setDragStartSelectedTime(selectedTime);
    setHasMoved(false); // Reset movement tracking

    // Pause playback if dragging
    if (isPlaying) {
      setIsPlaying(false);
    }
  };

  // Handle marker drag
  useEffect(() => {
    const handleDrag = (e: MouseEvent) => {
      if (
        !isDraggingMarker ||
        !timelineRef.current ||
        timeIntervals.length === 0
      )
        return;

      const rect = timelineRef.current.getBoundingClientRect();
      const dragPosition = e.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, dragPosition / rect.width));

      // Find the closest time interval
      const index = Math.min(
        Math.floor(percentage * timeIntervals.length),
        timeIntervals.length - 1
      );

      // Use the exact time from the interval
      updateSelectedTime(timeIntervals[index].time);
    };

    const handleDragEnd = () => {
      setIsDraggingMarker(false);
    };

    if (isDraggingMarker) {
      window.addEventListener("mousemove", handleDrag);
      window.addEventListener("mouseup", handleDragEnd);
    }

    return () => {
      window.removeEventListener("mousemove", handleDrag);
      window.removeEventListener("mouseup", handleDragEnd);
    };
  }, [isDraggingMarker, timeIntervals, onTimeChange]);

  // Handle timeline drag
  useEffect(() => {
    const handleDrag = (e: MouseEvent) => {
      if (
        !isDraggingTimeline ||
        !timelineRef.current ||
        !dragStartTime ||
        !dragStartSelectedTime
      )
        return;

      // Check if mouse has moved significantly
      const dragDeltaX = e.clientX - dragStartX;
      if (Math.abs(dragDeltaX) > 5) {
        setHasMoved(true);
      }

      const rect = timelineRef.current.getBoundingClientRect();
      const timelineWidth = rect.width;

      // Calculate time shift based on drag distance
      // Full timeline width = lookbackHours hours, so calculate minutes per pixel
      const minutesPerPixel = (lookbackHours * 60) / timelineWidth;
      const minutesShift = dragDeltaX * minutesPerPixel;

      // Shift the end time (and consequently the start time)
      const newEndTime = dragStartTime.subtract(minutesShift, "minute");

      // Also shift the selected time by the same amount
      const newSelectedTime = dragStartSelectedTime.subtract(
        minutesShift,
        "minute"
      );

      // Update both times
      setCurrentTime(roundToNearestTenMinutes(newEndTime));
      updateSelectedTime(newSelectedTime);
    };

    const handleDragEnd = () => {
      setIsDraggingTimeline(false);
      setDragStartTime(null);
      setDragStartSelectedTime(null);

      // Set the recently dragged flag to prevent immediate click
      setRecentlyDragged(true);

      // Reset the flag after a short delay
      setTimeout(() => {
        setRecentlyDragged(false);
        setHasMoved(false);
      }, 300); // 300ms should be enough to prevent accidental clicks
    };

    if (isDraggingTimeline) {
      window.addEventListener("mousemove", handleDrag);
      window.addEventListener("mouseup", handleDragEnd);
    }

    return () => {
      window.removeEventListener("mousemove", handleDrag);
      window.removeEventListener("mouseup", handleDragEnd);
    };
  }, [
    isDraggingTimeline,
    dragStartX,
    dragStartTime,
    dragStartSelectedTime,
    lookbackHours,
  ]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();

        if (timeIntervals.length === 0) return;

        // Find current index
        const currentIndex = timeIntervals.findIndex(
          (interval) => interval.time.format() === selectedTime.format()
        );

        if (currentIndex === -1) return;

        // Calculate new index
        let newIndex = currentIndex + (e.key === "ArrowLeft" ? -1 : 1);

        // Ensure we stay within bounds
        newIndex = Math.max(0, Math.min(newIndex, timeIntervals.length - 1));

        updateSelectedTime(timeIntervals[newIndex].time);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedTime, timeIntervals]);

  // Handle playback
  useEffect(() => {
    if (!isPlaying || timeIntervals.length === 0) return;

    const currentIndex = timeIntervals.findIndex(
      (interval) => interval.time.format() === selectedTime.format()
    );

    // If at the end or not found, stop playback
    if (currentIndex === -1 || currentIndex >= timeIntervals.length - 1) {
      setIsPlaying(false);
      return;
    }

    // Set up timer to advance to next interval
    const timer = setTimeout(() => {
      const nextIndex = currentIndex + 1;
      if (nextIndex < timeIntervals.length) {
        updateSelectedTime(timeIntervals[nextIndex].time);
      } else {
        setIsPlaying(false);
      }
    }, 500); // Fixed speed of 500ms per step

    return () => clearTimeout(timer);
  }, [isPlaying, selectedTime, timeIntervals]);

  // Toggle play/pause
  const togglePlayback = () => {
    if (isPlaying) {
      setIsPlaying(false);
    } else {
      // If at the end, restart from beginning
      if (selectedTime.format() === currentTime.format()) {
        updateSelectedTime(getStartTime());
      }
      setIsPlaying(true);
    }
  };

  // Calculate marker position based on time intervals
  const getMarkerPosition = () => {
    if (timeIntervals.length === 0) return 0;

    // Find the index of the selected time in the intervals
    const index = timeIntervals.findIndex(
      (interval) => interval.time.format() === selectedTime.format()
    );

    // If not found, find the closest interval
    if (index === -1) {
      let closestIndex = 0;
      let minDiff = Number.POSITIVE_INFINITY;

      timeIntervals.forEach((interval, i) => {
        const diff = Math.abs(interval.time.diff(selectedTime));
        if (diff < minDiff) {
          minDiff = diff;
          closestIndex = i;
        }
      });

      return (closestIndex / (timeIntervals.length - 1)) * 100;
    }

    return (index / (timeIntervals.length - 1)) * 100;
  };

  // Handle lookback hours change
  const handleLookbackChange = (hours: number) => {
    setLookbackHours(hours);
  };

  // Handle end time change
  const handleEndTimeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEndTime = parseDateTimeInput(e.target.value);
    setCurrentTime(roundToNearestTenMinutes(newEndTime));
  };

  // Keyboard event handling, blocking bubbling and default behavior, and handling left and right keys
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();

      if (timeIntervals.length === 0) return;

      // Find current index
      const currentIndex = timeIntervals.findIndex(
        (interval) => interval.time.format() === selectedTime.format()
      );

      if (currentIndex === -1) return;

      // Calculate new index
      let newIndex = currentIndex + (e.key === "ArrowLeft" ? -1 : 1);

      // Ensure we stay within bounds
      newIndex = Math.max(0, Math.min(newIndex, timeIntervals.length - 1));

      updateSelectedTime(timeIntervals[newIndex].time);
    }
  };

  return (
    <div tabIndex={0} onKeyDown={handleKeyDown} className="time-range-selector">
      <div className="time-range-header">
        <div className="time-controls">
          {/* Play/Pause button */}
          <button
            className={`play-button ${isPlaying ? "playing" : ""}`}
            onClick={togglePlayback}
          >
            {isPlaying ? "Pause" : "Play"}
          </button>

          {/* Datetime picker */}
          <div className="datetime-picker">
            <input
              type="datetime-local"
              value={formatDateTimeInput(currentTime)}
              onChange={handleEndTimeChange}
            />
          </div>

          {/* Lookback hours selector */}
          <select
            className="lookback-selector"
            value={lookbackHours}
            onChange={(e) => handleLookbackChange(Number(e.target.value))}
          >
            <option value={6}>Last 6 hours</option>
            <option value={12}>Last 12 hours</option>
            <option value={24}>Last 24 hours</option>
          </select>
        </div>
      </div>

      <div className="time-range-info">
        <div className="start-time">
          Start: {formatFullDateTime(getStartTime())}
        </div>
        <div className="end-time">End: {formatFullDateTime(getEndTime())}</div>
      </div>

      <div
        ref={timelineRef}
        className={`timeline ${isDraggingTimeline ? "dragging" : ""}`}
        onClick={handleTimelineClick}
        onMouseDown={handleTimelineDragStart}
      >
        {/* Render tick marks and labels */}
        {timeIntervals.map((interval, index) => {
          // Calculate position as percentage
          const position =
            timeIntervals.length > 1
              ? (index / (timeIntervals.length - 1)) * 100
              : 50;

          return (
            <div
              key={index}
              className="time-interval"
              style={{
                left: `${position}%`,
              }}
            >
              {/* Tick container for vertical centering */}
              <div className="tick-container">
                {/* Tick mark */}
                <div
                  className={`tick-mark ${interval.isHour ? "hour" : ""}`}
                ></div>
              </div>

              {/* Hour label */}
              {interval.isHour && (
                <div className="time-label">{interval.label}</div>
              )}
            </div>
          );
        })}

        {/* Selected time marker with time display above */}
        {timeIntervals.length > 0 && (
          <div
            ref={markerRef}
            className={`time-marker ${isPlaying ? "playing" : ""} ${
              isDraggingMarker ? "dragging" : ""
            }`}
            style={{ left: `${getMarkerPosition()}%` }}
            onMouseDown={handleMarkerDragStart}
          >
            {/* Time display above the marker */}
            <div className="marker-label">
              {formatFullDateTime(selectedTime)}
            </div>

            {/* Triangle pointer */}
            <div className="marker-pointer"></div>
          </div>
        )}
      </div>
    </div>
  );
}
