import type React from "react";

import { useEffect, useRef, useState, useCallback } from "react";
import { useMap } from "react-leaflet";

import dayjs from "dayjs";

import type { TimeDimensionLayerHandles } from "./time-dimension-layer";
import "./side-by-side.css";

interface SideBySideProps {
  leftLayer: TimeDimensionLayerHandles;
  rightLayer: TimeDimensionLayerHandles;
  selectedTime?: dayjs.Dayjs;
  initialPosition?: number;
}

export default function SideBySide({
  leftLayer,
  rightLayer,
  selectedTime,
  initialPosition = 50,
}: SideBySideProps) {
  const map = useMap();
  const [position, setPosition] = useState(initialPosition);
  const positionRef = useRef(initialPosition); // Use ref to track current position for real-time updates
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Function to update the clip rectangles - extracted as a callback so it can be called from multiple places
  const updateClip = useCallback(() => {
    if (!map || !leftLayer || !rightLayer) return;

    const mapSize = map.getSize();
    const nw = map.containerPointToLayerPoint([0, 0]);
    const se = map.containerPointToLayerPoint(mapSize);
    const clipX = nw.x + (mapSize.x * positionRef.current) / 100;

    // Set clip paths for both layers
    const currentLeftLayer = leftLayer.getCurrentLayer();
    const currentRightLayer = rightLayer.getCurrentLayer();
    const leftContainer = currentLeftLayer?.getContainer();
    const rightContainer = currentRightLayer?.getContainer();

    if (leftContainer) {
      // Left layer - show only left side of divider
      leftContainer.style.clipPath = `polygon(${nw.x}px ${nw.y}px, ${clipX}px ${nw.y}px, ${clipX}px ${se.y}px, ${nw.x}px ${se.y}px)`;
    }

    if (rightContainer) {
      // Right layer - show only right side of divider
      rightContainer.style.clipPath = `polygon(${clipX}px ${nw.y}px, ${se.x}px ${nw.y}px, ${se.x}px ${se.y}px, ${clipX}px ${se.y}px)`;
    }
  }, [map, leftLayer, rightLayer]);

  // Update clip when selected time changes (e.g., when TimeDimensionLayer switches to a different cached layer)
  useEffect(() => {
    // Use requestAnimationFrame to synchronize with browser repaint
    const rafId = requestAnimationFrame(() => {
      updateClip();
    });

    return () => cancelAnimationFrame(rafId);
  }, [selectedTime, updateClip]);

  // Initialize the control
  useEffect(() => {
    if (!map || !leftLayer || !rightLayer) return;

    // Update clip on map events
    const onMoveEnd = () => updateClip();
    const onZoomEnd = () => updateClip();
    const onResize = () => updateClip();
    const onMove = () => updateClip(); // Add handler for move event for more responsive updates
    const onLayerAdd = () => {
      // Defer to next frame so the layer's DOM container is fully attached
      requestAnimationFrame(updateClip);
    };

    map.on("moveend", onMoveEnd);
    map.on("zoomend", onZoomEnd);
    map.on("resize", onResize);
    map.on("move", onMove); // Listen for move events
    map.on("layeradd", onLayerAdd);

    // Initial update with delay
    setTimeout(updateClip, 100);

    // Cleanup
    return () => {
      map.off("moveend", onMoveEnd);
      map.off("zoomend", onZoomEnd);
      map.off("resize", onResize);
      map.off("move", onMove);
      map.off("layeradd", onLayerAdd);

      // Get all cached layers from both layer handles
      const leftLayers = leftLayer.getCachedLayers();
      const rightLayers = rightLayer.getCachedLayers();

      // Reset clip paths for all layer containers
      [...leftLayers, ...rightLayers].forEach((layer) => {
        const container = layer.getContainer();
        if (container) {
          container.style.clipPath = "none";
        }
      });
    };
  }, [map, leftLayer, rightLayer, updateClip]);

  // Handle divider drag
  const handleDragStart = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);

    // Disable map dragging
    if (map.dragging.enabled()) {
      map.dragging.disable();
    }
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleDrag = (e: MouseEvent | TouchEvent) => {
      if (!containerRef.current) return;

      e.preventDefault();
      e.stopPropagation();

      const rect = containerRef.current.getBoundingClientRect();
      const x = "touches" in e ? e.touches[0].clientX : e.clientX;
      const pos = Math.max(
        0,
        Math.min(100, ((x - rect.left) / rect.width) * 100)
      );

      // Update ref immediately for real-time effect
      positionRef.current = pos;

      // Update clip immediately
      updateClip();

      // Also update state (this will be batched by React)
      setPosition(pos);
    };

    const handleDragEnd = () => {
      setIsDragging(false);

      // Re-enable map dragging
      if (map && !map.dragging.enabled()) {
        map.dragging.enable();
      }
    };

    document.addEventListener("mousemove", handleDrag);
    document.addEventListener("touchmove", handleDrag, { passive: false });
    document.addEventListener("mouseup", handleDragEnd);
    document.addEventListener("touchend", handleDragEnd);

    return () => {
      document.removeEventListener("mousemove", handleDrag);
      document.removeEventListener("touchmove", handleDrag);
      document.removeEventListener("mouseup", handleDragEnd);
      document.removeEventListener("touchend", handleDragEnd);
    };
  }, [isDragging, map, updateClip]);

  return (
    <div ref={containerRef} className="side-by-side-container">
      <div
        className={`side-by-side-divider ${isDragging ? "dragging" : ""}`}
        style={{ left: `${position}%` }}
        onMouseDown={handleDragStart}
        onTouchStart={handleDragStart}
      >
        <div className="divider-line"></div>
        <div className="divider-slider"></div>
      </div>
    </div>
  );
}
