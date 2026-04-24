import type React from "react";
import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import dayjs from "dayjs";
import { ChevronDown } from "lucide-react";
import { useIsMobile } from "../hooks/use-mobile";
import { roundToNearestTenMinutes } from "../utils/time-utils";
import "./time-range-selector.css";

// Format time as HH:MM
const formatTime = (date: dayjs.Dayjs): string => {
  return date.format("HH:mm");
};

// Format date only as MM-DD (shorter format)
const formatDate = (date: dayjs.Dayjs): string => {
  return date.format("MM-DD");
};

// Format full date and time as YYYY-MM-DD HH:MM
const formatFullDateTime = (date: dayjs.Dayjs): string => {
  return date.format("YYYY-MM-DD HH:mm");
};

// Format date for datetime-local input
const formatDateTimeInput = (date: dayjs.Dayjs): string => {
  return date.format("YYYY-MM-DDTHH:mm");
};

interface TimeRangeSelectorProps {
  selectedTime: dayjs.Dayjs;
  latestCompositeTime?: dayjs.Dayjs;
  onSelectedTimeChange?: (time: dayjs.Dayjs) => void;
  onTimeRangeChange?: (startTime: dayjs.Dayjs, endTime: dayjs.Dayjs) => void;
  isBuffering?: boolean;
}

export default function TimeRangeSelector({
  selectedTime,
  latestCompositeTime,
  onSelectedTimeChange,
  onTimeRangeChange,
  isBuffering = false
}: TimeRangeSelectorProps) {
  const [timelineTime, setTimelineTime] = useState<dayjs.Dayjs>(
    roundToNearestTenMinutes(selectedTime || dayjs().utc())
  );
  const [lookbackHours, setLookbackHours] = useState<number>(6); // Default to 6 hours lookback
  const [isDraggingMarker, setIsDraggingMarker] = useState<boolean>(false);
  const [isDraggingTimeline, setIsDraggingTimeline] = useState<boolean>(false);
  const [dragStartX, setDragStartX] = useState<number>(0);
  const [dragStartTime, setDragStartTime] = useState<dayjs.Dayjs | null>(null);
  const [dragStartSelectedTime, setDragStartSelectedTime] =
    useState<dayjs.Dayjs | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [recentlyDragged, setRecentlyDragged] = useState<boolean>(false);
  const [hasMoved, setHasMoved] = useState<boolean>(false); // Track if mouse has moved during drag
  const [isCtrlPressed, setIsCtrlPressed] = useState<boolean>(false);
  const [isLookbackOpen, setIsLookbackOpen] = useState<boolean>(false);
  const timelineRef = useRef<HTMLDivElement>(null);
  const markerRef = useRef<HTMLDivElement>(null);
  const lookbackDropdownRef = useRef<HTMLDivElement>(null);
  const bufferingTimerRef = useRef<dayjs.Dayjs | null>(null);
  const isMobile = useIsMobile();

  // Calculate start time based on current time and lookback hours
  const getStartTime = (): dayjs.Dayjs => {
    return timelineTime.subtract(lookbackHours, "hour");
  };

  // Calculate end time (always current time)
  const getEndTime = (): dayjs.Dayjs => {
    return timelineTime;
  };

  // Generate time intervals for the timeline
  const timeIntervals = useMemo(() => {
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

      // Check if it is after the latest composite time
      const isAfterLatest = latestCompositeTime
        ? time.isAfter(latestCompositeTime)
        : false;

      // Check if this is midnight (start of a new day)
      const isMidnight = time.hour() === 0 && time.minute() === 0;

      intervals.push({
        time: time,
        label: formatTime(time), // Always show time at the bottom
        dateLabel: isMidnight ? formatDate(time) : null, // Show date at the top for midnight
        isHour: time.minute() === 0,
        isMidnight: isMidnight,
        isAfterLatest: isAfterLatest
      });
    }

    return intervals;
  }, [timelineTime, lookbackHours, latestCompositeTime]);

  // Find the closest time interval index for a given time
  const findClosestIntervalIndex = (targetTime: dayjs.Dayjs): number => {
    if (timeIntervals.length === 0) return -1;

    // First try to find exact match
    const exactIndex = timeIntervals.findIndex(
      (interval) => interval.time.valueOf() === targetTime.valueOf()
    );

    if (exactIndex !== -1) return exactIndex;

    // If no exact match, find the closest one
    let closestIndex = 0;
    let minDiff = Number.POSITIVE_INFINITY;

    timeIntervals.forEach((interval, i) => {
      if (interval && interval.time) {
        const diff = Math.abs(interval.time.diff(targetTime, "millisecond"));
        if (diff < minDiff) {
          minDiff = diff;
          closestIndex = i;
        }
      }
    });

    return closestIndex;
  };

  // Calculate marker position using useMemo
  const markerPosition = useMemo(() => {
    if (timeIntervals.length === 0) return 0;

    const index = findClosestIntervalIndex(selectedTime);

    if (index === -1) return 0;

    return (index / (timeIntervals.length - 1)) * 100;
  }, [timeIntervals, selectedTime]);

  // Update selected time and ensure it's rounded to nearest 10 minutes
  const updateSelectedTime = useCallback(
    (time: dayjs.Dayjs) => {
      const roundedTime = roundToNearestTenMinutes(time);
      onSelectedTimeChange?.(roundedTime);
    },
    [onSelectedTimeChange]
  );

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

    // Add additional safety checks
    if (index < 0 || index >= timeIntervals.length) return;
    if (!timeIntervals[index] || !timeIntervals[index].time) return;

    // Use the exact time from the interval
    updateSelectedTime(timeIntervals[index].time);
  };

  // Handle marker drag start
  const handleMarkerDragStart = (
    e: React.MouseEvent<HTMLDivElement> | React.TouchEvent<HTMLDivElement>
  ) => {
    e.preventDefault();
    e.stopPropagation(); // Prevent timeline drag
    setIsDraggingMarker(true);
    // Pause playback if dragging
    if (isPlaying) {
      setIsPlaying(false);
    }
  };

  // Handle timeline drag start
  const handleTimelineDragStart = (
    e: React.MouseEvent<HTMLDivElement> | React.TouchEvent<HTMLDivElement>
  ) => {
    // Only start timeline drag if we're not dragging the marker
    if (isDraggingMarker) return;

    e.preventDefault();
    setIsDraggingTimeline(true);

    // Get the starting X position (works for both mouse and touch)
    const startX =
      "touches" in e ? e.touches[0].clientX : (e as React.MouseEvent).clientX;

    setDragStartX(startX);
    setDragStartTime(timelineTime);
    setDragStartSelectedTime(selectedTime);
    setHasMoved(false); // Reset movement tracking

    // Pause playback if dragging
    if (isPlaying) {
      setIsPlaying(false);
    }
  };

  // Handle marker drag
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
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

      // Add safety check
      if (index < 0 || index >= timeIntervals.length) return;
      if (!timeIntervals[index] || !timeIntervals[index].time) return;

      // Use the exact time from the interval
      updateSelectedTime(timeIntervals[index].time);
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (
        !isDraggingMarker ||
        !timelineRef.current ||
        timeIntervals.length === 0
      )
        return;

      const rect = timelineRef.current.getBoundingClientRect();
      const dragPosition = e.touches[0].clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, dragPosition / rect.width));

      // Find the closest time interval
      const index = Math.min(
        Math.floor(percentage * timeIntervals.length),
        timeIntervals.length - 1
      );

      // Add safety check
      if (index < 0 || index >= timeIntervals.length) return;
      if (!timeIntervals[index] || !timeIntervals[index].time) return;

      // Use the exact time from the interval
      updateSelectedTime(timeIntervals[index].time);
    };

    const handleDragEnd = () => {
      setIsDraggingMarker(false);
    };

    if (isDraggingMarker) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("touchmove", handleTouchMove, {
        passive: false
      });
      document.addEventListener("mouseup", handleDragEnd);
      document.addEventListener("touchend", handleDragEnd);
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("touchmove", handleTouchMove);
      document.removeEventListener("mouseup", handleDragEnd);
      document.removeEventListener("touchend", handleDragEnd);
    };
  }, [isDraggingMarker, timeIntervals, updateSelectedTime]);

  // Handle timeline drag
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
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

      // Calculate the new end time
      const newEndTime = dragStartTime.subtract(minutesShift, "minute");

      // Prevent dragging if the new end time would be greater than current time
      const currentRealTime = dayjs().utc();
      if (newEndTime.isAfter(currentRealTime)) {
        return;
      }

      // Also shift the selected time by the same amount
      const newSelectedTime = dragStartSelectedTime.subtract(
        minutesShift,
        "minute"
      );

      // Update both times
      setTimelineTime(roundToNearestTenMinutes(newEndTime));
      updateSelectedTime(newSelectedTime);
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (
        !isDraggingTimeline ||
        !timelineRef.current ||
        !dragStartTime ||
        !dragStartSelectedTime
      )
        return;

      e.preventDefault(); // Prevent scrolling while dragging

      // Check if touch has moved significantly
      const dragDeltaX = e.touches[0].clientX - dragStartX;
      if (Math.abs(dragDeltaX) > 5) {
        setHasMoved(true);
      }

      const rect = timelineRef.current.getBoundingClientRect();
      const timelineWidth = rect.width;

      // Calculate time shift based on drag distance
      const minutesPerPixel = (lookbackHours * 60) / timelineWidth;
      const minutesShift = dragDeltaX * minutesPerPixel;

      // Calculate the new end time
      const newEndTime = dragStartTime.subtract(minutesShift, "minute");

      // Prevent dragging if the new end time would be greater than current time
      const currentRealTime = dayjs().utc();
      if (newEndTime.isAfter(currentRealTime)) {
        return;
      }

      // Also shift the selected time by the same amount
      const newSelectedTime = dragStartSelectedTime.subtract(
        minutesShift,
        "minute"
      );

      // Update both times
      setTimelineTime(roundToNearestTenMinutes(newEndTime));
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
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("touchmove", handleTouchMove, {
        passive: false
      });
      document.addEventListener("mouseup", handleDragEnd);
      document.addEventListener("touchend", handleDragEnd);
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("touchmove", handleTouchMove);
      document.removeEventListener("mouseup", handleDragEnd);
      document.removeEventListener("touchend", handleDragEnd);
    };
  }, [
    isDraggingTimeline,
    dragStartX,
    dragStartTime,
    dragStartSelectedTime,
    lookbackHours,
    updateSelectedTime
  ]);

  // Toggle play/pause
  const togglePlayback = useCallback(() => {
    if (isPlaying) {
      setIsPlaying(false);
    } else {
      // If at the end, restart from beginning
      if (selectedTime.valueOf() === timelineTime.valueOf()) {
        updateSelectedTime(getStartTime());
      } else {
        // Ensure the selected time is in the timeIntervals array
        const currentIndex = findClosestIntervalIndex(selectedTime);

        // If current time is not found in intervals, snap to the closest one
        if (currentIndex !== -1 && timeIntervals[currentIndex]) {
          const exactIndex = timeIntervals.findIndex(
            (interval) => interval.time.valueOf() === selectedTime.valueOf()
          );

          // If not exact match, update to the closest valid time before starting playback
          if (exactIndex === -1 && timeIntervals[currentIndex].time) {
            updateSelectedTime(timeIntervals[currentIndex].time);
          }
        }
      }
      setIsPlaying(true);
    }
  }, [
    isPlaying,
    selectedTime,
    timelineTime,
    timeIntervals,
    updateSelectedTime
  ]);

  // Handle keyboard navigation and playback control
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if focus is on an input element or dropdown is open
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "SELECT" ||
        target.tagName === "TEXTAREA" ||
        isLookbackOpen
      )
        return;

      // Handle spacebar for play/pause
      if (e.key === " " || e.key === "Spacebar") {
        e.preventDefault(); // Prevent page scrolling
        e.stopPropagation(); // Prevent event bubbling
        togglePlayback();
        return;
      }

      // Handle arrow keys for navigation
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        e.stopPropagation();

        if (timeIntervals.length === 0) return;

        // Find current index
        const currentIndex = timeIntervals.findIndex(
          (interval) => interval.time.valueOf() === selectedTime.valueOf()
        );

        if (currentIndex === -1) return;

        // Calculate new index
        let newIndex = currentIndex + (e.key === "ArrowLeft" ? -1 : 1);

        // Ensure we stay within bounds
        newIndex = Math.max(0, Math.min(newIndex, timeIntervals.length - 1));

        // Add safety check
        if (!timeIntervals[newIndex] || !timeIntervals[newIndex].time) return;

        updateSelectedTime(timeIntervals[newIndex].time);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [
    selectedTime,
    timeIntervals,
    togglePlayback,
    updateSelectedTime,
    isLookbackOpen
  ]);

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

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("keyup", handleKeyUp);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  // Handle playback
  useEffect(() => {
    if (!isPlaying || timeIntervals.length === 0) return;

    let timeoutId: ReturnType<typeof setTimeout>;
    let isCancelled = false;

    const playback = () => {
      if (isCancelled) return;

      const currentIndex = timeIntervals.findIndex(
        (interval) => interval.time.valueOf() === selectedTime.valueOf()
      );

      // If at the end or not found, stop playback
      if (currentIndex === -1 || currentIndex >= timeIntervals.length - 1) {
        setIsPlaying(false);
        bufferingTimerRef.current = null;
        return;
      }

      // If buffering is enabled and currently buffering
      if (isBuffering) {
        // Record when buffering started
        if (!bufferingTimerRef.current) {
          bufferingTimerRef.current = dayjs();
        }

        // Check if buffering timeout exceeded
        const bufferingDuration = dayjs().diff(bufferingTimerRef.current);
        if (bufferingDuration < 3000) {
          // Still waiting for buffer, check again later
          timeoutId = setTimeout(playback, 100);
          return;
        } else {
          // Force playback to continue despite buffering
          console.log(
            `buffering timeout exceeded (${bufferingDuration}ms), forcing playback to continue`
          );
          bufferingTimerRef.current = null;
        }
      } else {
        // Not buffering, reset the timer
        bufferingTimerRef.current = null;
      }

      // Set up timer to advance to next interval
      timeoutId = setTimeout(() => {
        const nextIndex = currentIndex + 1;
        if (
          nextIndex < timeIntervals.length &&
          timeIntervals[nextIndex] &&
          timeIntervals[nextIndex].time
        ) {
          updateSelectedTime(timeIntervals[nextIndex].time);
        } else {
          setIsPlaying(false);
        }
      }, 500);
    };

    playback();

    return () => {
      isCancelled = true;
      clearTimeout(timeoutId);
    };
  }, [isPlaying, selectedTime, timeIntervals, updateSelectedTime, isBuffering]);

  // Handle lookback hours change
  const handleLookbackChange = (hours: number) => {
    setLookbackHours(hours);
  };

  // Close lookback dropdown when clicking outside or pressing Escape
  useEffect(() => {
    if (!isLookbackOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (
        lookbackDropdownRef.current &&
        !lookbackDropdownRef.current.contains(event.target as Node)
      ) {
        setIsLookbackOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault(); // Prevent page scrolling
        event.stopPropagation(); // Prevent event bubbling
        setIsLookbackOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isLookbackOpen]);

  // Handle end time change
  const handleTimelineChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const currentTime = dayjs().utc();
    const newTime = dayjs(e.target.value);

    // Prevent selecting future dates
    const roundedTime = roundToNearestTenMinutes(
      newTime.isAfter(currentTime) ? currentTime : newTime
    );

    onSelectedTimeChange?.(roundedTime);
  };

  // Add an effect to handle changes to selectedTime prop
  useEffect(() => {
    if (selectedTime) {
      // Update the selected time without changing the time range
      // If the selected time is outside the current range, update the range
      const startTime = getStartTime();
      const endTime = getEndTime();

      if (selectedTime.isBefore(startTime) || selectedTime.isAfter(endTime)) {
        setTimelineTime(selectedTime);
      }
    }
  }, [selectedTime, lookbackHours, timelineTime]);

  // Notify parent component of time range change
  useEffect(() => {
    const startTime = getStartTime();
    const endTime = getEndTime();
    onTimeRangeChange?.(startTime, endTime);
  }, [timelineTime, lookbackHours, onTimeRangeChange]);

  return (
    <div className={`time-range-selector ${isMobile ? "mobile" : ""}`}>
      <div className="time-controls-container">
        <div className="time-controls">
          {/* Play/Pause button */}
          <button
            className={`play-button ${isPlaying ? "playing" : ""}`}
            onClick={togglePlayback}
          >
            {isPlaying ? "Pause" : "Play"}
          </button>

          {/* Lookback hours selector */}
          <div className="lookback-wrapper" ref={lookbackDropdownRef}>
            <button
              className="lookback-button"
              onClick={() => setIsLookbackOpen(!isLookbackOpen)}
            >
              Last {lookbackHours} hours
              <ChevronDown size={14} className="dropdown-icon" />
            </button>
            {isLookbackOpen && (
              <div className="lookback-dropdown">
                {[6, 12, 24].map((hours) => (
                  <div
                    key={hours}
                    className={`lookback-option ${
                      lookbackHours === hours ? "selected" : ""
                    }`}
                    onClick={() => {
                      handleLookbackChange(hours);
                      setIsLookbackOpen(false);
                    }}
                  >
                    Last {hours} hours
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Datetime picker */}
          <div className="datetime-picker">
            <input
              type="datetime-local"
              value={formatDateTimeInput(timelineTime)}
              onChange={handleTimelineChange}
              max={formatDateTimeInput(dayjs().utc())}
            />
          </div>
        </div>
      </div>

      <div className="timeline-container">
        <div
          ref={timelineRef}
          className={`timeline ${isDraggingTimeline ? "dragging" : ""}`}
          onClick={handleTimelineClick}
          onMouseDown={handleTimelineDragStart}
          onTouchStart={handleTimelineDragStart}
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
                className={`time-interval ${
                  interval.isAfterLatest ? "after-latest" : ""
                }`}
                style={{
                  left: `${position}%`
                }}
              >
                {/* Date label for midnight (inside the timeline) */}
                {interval.dateLabel && (
                  <div className="date-label">{interval.dateLabel}</div>
                )}

                {/* Tick container for vertical centering */}
                <div className="tick-container">
                  {/* Tick mark */}
                  <div
                    className={`tick-mark ${interval.isHour ? "hour" : ""}`}
                  ></div>
                </div>

                {/* Hour label (below the tick) */}
                {interval.isHour && (
                  <div className="time-label">{interval.label}</div>
                )}
              </div>
            );
          })}

          {/* Overlay for darkening left side when Ctrl is pressed */}
          {isCtrlPressed && timeIntervals.length > 0 && (
            <div
              className="timeline-overlay"
              style={{
                left: "0%",
                width: `${markerPosition}%`
              }}
            />
          )}

          {/* Selected time marker with time display above */}
          {timeIntervals.length > 0 && (
            <div
              ref={markerRef}
              className={`time-marker ${isPlaying ? "playing" : ""} ${
                isDraggingMarker ? "dragging" : ""
              }`}
              style={{ left: `${markerPosition}%` }}
              onMouseDown={handleMarkerDragStart}
              onTouchStart={handleMarkerDragStart}
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
    </div>
  );
}
