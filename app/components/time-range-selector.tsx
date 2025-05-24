import type React from "react";
import { useEffect, useRef, useState } from "react";
import dayjs from "dayjs";
import { useIsMobile } from "../hooks/use-mobile";
import "./time-range-selector.css";

interface TimeRangeSelectorProps {
  initialTime?: Date | string | dayjs.Dayjs;
  selectedTime?: dayjs.Dayjs | null;
  onTimeChange?: (time: dayjs.Dayjs) => void;
}

export default function TimeRangeSelector({
  initialTime = dayjs().utc(),
  selectedTime = null,
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
    roundToNearestTenMinutes(dayjs().utc())
  );
  const [selectedTimeState, setSelectedTime] = useState<dayjs.Dayjs>(
    roundToNearestTenMinutes(initialTime)
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
  const timelineRef = useRef<HTMLDivElement>(null);
  const markerRef = useRef<HTMLDivElement>(null);
  const [timeIntervals, setTimeIntervals] = useState<any[]>([]);
  const isMobile = useIsMobile();

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

      // Check if this is midnight (start of a new day)
      const isMidnight = time.hour() === 0 && time.minute() === 0;

      intervals.push({
        time: time,
        label: formatTime(time), // Always show time at the bottom
        dateLabel: isMidnight ? formatDate(time) : null, // Show date at the top for midnight
        isHour: time.minute() === 0,
        isHalfHour: time.minute() === 30,
        isMidnight: isMidnight,
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

    if (selectedTimeState.isBefore(startTime)) {
      updateSelectedTime(startTime);
    } else if (selectedTimeState.isAfter(endTime)) {
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
    setDragStartTime(currentTime);
    setDragStartSelectedTime(selectedTimeState);
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
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("touchmove", handleTouchMove, { passive: false });
      window.addEventListener("mouseup", handleDragEnd);
      window.addEventListener("touchend", handleDragEnd);
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("touchmove", handleTouchMove);
      window.removeEventListener("mouseup", handleDragEnd);
      window.removeEventListener("touchend", handleDragEnd);
    };
  }, [isDraggingMarker, timeIntervals, onTimeChange]);

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
      setCurrentTime(roundToNearestTenMinutes(newEndTime));
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
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("touchmove", handleTouchMove, { passive: false });
      window.addEventListener("mouseup", handleDragEnd);
      window.addEventListener("touchend", handleDragEnd);
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("touchmove", handleTouchMove);
      window.removeEventListener("mouseup", handleDragEnd);
      window.removeEventListener("touchend", handleDragEnd);
    };
  }, [
    isDraggingTimeline,
    dragStartX,
    dragStartTime,
    dragStartSelectedTime,
    lookbackHours,
  ]);

  // Handle keyboard navigation and playback control
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Handle spacebar for play/pause
      if (e.key === " " || e.key === "Spacebar") {
        e.preventDefault(); // Prevent page scrolling
        togglePlayback();
        return;
      }

      // Handle arrow keys for navigation
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();

        if (timeIntervals.length === 0) return;

        // Find current index
        const currentIndex = timeIntervals.findIndex(
          (interval) => interval.time.format() === selectedTimeState.format()
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

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedTimeState, timeIntervals]);

  // Handle playback
  useEffect(() => {
    if (!isPlaying || timeIntervals.length === 0) return;

    const currentIndex = timeIntervals.findIndex(
      (interval) => interval.time.format() === selectedTimeState.format()
    );

    // If at the end or not found, stop playback
    if (currentIndex === -1 || currentIndex >= timeIntervals.length - 1) {
      setIsPlaying(false);
      return;
    }

    // Set up timer to advance to next interval
    const timer = setTimeout(() => {
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
    }, 500); // Fixed speed of 500ms per step

    return () => clearTimeout(timer);
  }, [isPlaying, selectedTimeState, timeIntervals]);

  // Toggle play/pause
  const togglePlayback = () => {
    if (isPlaying) {
      setIsPlaying(false);
    } else {
      // If at the end, restart from beginning
      if (selectedTimeState.format() === currentTime.format()) {
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
      (interval) => interval.time.format() === selectedTimeState.format()
    );

    // If not found, find the closest interval
    if (index === -1) {
      let closestIndex = 0;
      let minDiff = Number.POSITIVE_INFINITY;

      timeIntervals.forEach((interval, i) => {
        if (interval && interval.time) {
          const diff = Math.abs(interval.time.diff(selectedTimeState));
          if (diff < minDiff) {
            minDiff = diff;
            closestIndex = i;
          }
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
    // Prevent selecting future dates
    const currentRealTime = dayjs().utc();
    let updatedEndTime;

    if (newEndTime.isAfter(currentRealTime)) {
      updatedEndTime = roundToNearestTenMinutes(currentRealTime);
    } else {
      updatedEndTime = roundToNearestTenMinutes(newEndTime);
    }

    setCurrentTime(updatedEndTime);
  };

  // Add an effect to handle changes to selectedTime prop
  useEffect(() => {
    if (selectedTime) {
      // Update the selected time without changing the time range
      setSelectedTime(roundToNearestTenMinutes(selectedTime));

      // If the selected time is outside the current range, update the range
      const startTime = getStartTime();
      const endTime = getEndTime();

      if (selectedTime.isBefore(startTime) || selectedTime.isAfter(endTime)) {
        // Calculate the earliest time that would include selectedTime in the timeline
        const currentRealTime = dayjs().utc();
        const earliestTime = currentRealTime.subtract(lookbackHours, "hour");

        if (earliestTime.isAfter(selectedTime)) {
          // selectedTime is too old, we need to extend the timeline to include it
          const newCurrentTime = roundToNearestTenMinutes(
            selectedTime.add(lookbackHours, "hour")
          );
          setCurrentTime(newCurrentTime);
        } else {
          // selectedTime can be included in current timeline, use current real time as end
          const newCurrentTime = roundToNearestTenMinutes(currentRealTime);
          setCurrentTime(newCurrentTime);
        }
      }
    }
  }, [selectedTime]);

  // Ensure timeIntervals is initialized before rendering
  useEffect(() => {
    if (timeIntervals.length === 0) {
      setTimeIntervals(generateTimeIntervals());
    }
  }, []);

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

          {/* Lookback hours selector*/}
          <div className="lookback-wrapper">
            <select
              className="lookback-selector"
              value={lookbackHours}
              onChange={(e) => handleLookbackChange(Number(e.target.value))}
            >
              <option value={6}>Last 6 hours</option>
              <option value={12}>Last 12 hours</option>
              <option value={24}>Last 24 hours</option>
            </select>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="select-icon"
            >
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>

          {/* Datetime picker */}
          <div className="datetime-picker">
            <input
              type="datetime-local"
              value={formatDateTimeInput(currentTime)}
              onChange={handleEndTimeChange}
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
                className="time-interval"
                style={{
                  left: `${position}%`,
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

          {/* Selected time marker with time display above */}
          {timeIntervals.length > 0 && (
            <div
              ref={markerRef}
              className={`time-marker ${isPlaying ? "playing" : ""} ${
                isDraggingMarker ? "dragging" : ""
              }`}
              style={{ left: `${getMarkerPosition()}%` }}
              onMouseDown={handleMarkerDragStart}
              onTouchStart={handleMarkerDragStart}
            >
              {/* Time display above the marker */}
              <div className="marker-label">
                {formatFullDateTime(selectedTimeState)}
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
