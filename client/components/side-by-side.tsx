import type React from "react";

import { useEffect, useRef, useState, useCallback } from "react";
import { useMap } from "react-leaflet";
import type L from "leaflet";
import "./side-by-side.css";

interface SideBySideProps {
  leftLayer: L.TileLayer;
  rightLayer: L.TileLayer;
  initialPosition?: number;
}

export default function SideBySide({
  leftLayer,
  rightLayer,
  initialPosition = 50,
}: SideBySideProps) {
  const map = useMap();
  const [position, setPosition] = useState(initialPosition);
  const positionRef = useRef(initialPosition); // Use ref to track current position for real-time updates
  const dividerRef = useRef<HTMLDivElement>(null);
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
    const leftContainer = leftLayer.getContainer();
    const rightContainer = rightLayer.getContainer();

    if (leftContainer && rightContainer) {
      // Left layer - show only left side of divider
      leftContainer.style.clipPath = `polygon(${nw.x}px ${nw.y}px, ${clipX}px ${nw.y}px, ${clipX}px ${se.y}px, ${nw.x}px ${se.y}px)`;

      // Right layer - show only right side of divider
      rightContainer.style.clipPath = `polygon(${clipX}px ${nw.y}px, ${se.x}px ${nw.y}px, ${se.x}px ${se.y}px, ${clipX}px ${se.y}px)`;
    }
  }, [map, leftLayer, rightLayer]);

  // Update ref when position state changes
  useEffect(() => {
    positionRef.current = position;
    updateClip();
  }, [position, updateClip]);

  // Initialize the control
  useEffect(() => {
    if (!map || !leftLayer || !rightLayer) return;

    // Make sure both layers are added to the map
    if (!map.hasLayer(leftLayer)) {
      map.addLayer(leftLayer);
    }
    if (!map.hasLayer(rightLayer)) {
      map.addLayer(rightLayer);
    }

    // Update clip on map events
    const onMoveEnd = () => updateClip();
    const onZoomEnd = () => updateClip();
    const onResize = () => updateClip();
    const onMove = () => updateClip(); // Add handler for move event for more responsive updates

    map.on("moveend", onMoveEnd);
    map.on("zoomend", onZoomEnd);
    map.on("resize", onResize);
    map.on("move", onMove); // Listen for move events

    // Initial update
    updateClip();

    // Cleanup
    return () => {
      map.off("moveend", onMoveEnd);
      map.off("zoomend", onZoomEnd);
      map.off("resize", onResize);
      map.off("move", onMove);

      // Reset clip paths
      const leftContainer = leftLayer.getContainer();
      const rightContainer = rightLayer.getContainer();

      if (leftContainer) leftContainer.style.clipPath = "none";
      if (rightContainer) rightContainer.style.clipPath = "none";
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
        ref={dividerRef}
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
