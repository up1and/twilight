import { useState, useRef, useEffect } from "react";
import { Layers, Check } from "lucide-react";
import "./layer-button.css";
import type { MapLayers } from "../utils/types";

interface LayerButtonProps {
  layers: MapLayers;
  onToggle: (layerId: keyof MapLayers) => void;
}

export default function LayerButton({ layers, onToggle }: LayerButtonProps) {
  const [isLayerOpen, setIsLayerOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        !dropdownRef.current?.contains(event.target as Node) &&
        !buttonRef.current?.contains(event.target as Node)
      ) {
        setIsLayerOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault(); // Prevent page scrolling
        event.stopPropagation(); // Prevent event bubbling
        setIsLayerOpen(false);
      }
    };

    if (isLayerOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isLayerOpen]);

  const handleToggle = () => {
    setIsLayerOpen(!isLayerOpen);
  };

  return (
    <div className="layer-button-container">
      <button
        ref={buttonRef}
        className="layer-button"
        onClick={handleToggle}
        aria-label="Layer Settings"
        title="Layer Settings"
      >
        <Layers size={16} />
      </button>

      {isLayerOpen && (
        <div ref={dropdownRef} className="layer-dropdown">
          <div className="layer-dropdown-header">Layers</div>
          <div
            className="layer-dropdown-item"
            onClick={() => onToggle("fir-boundary")}
          >
            <span className="layer-dropdown-label">FIR Boundary</span>
            {layers["fir-boundary"] && <Check size={14} strokeWidth={2.5} />}
          </div>
        </div>
      )}
    </div>
  );
}
