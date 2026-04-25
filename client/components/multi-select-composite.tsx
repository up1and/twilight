import { useState, useRef, useEffect } from "react";
import type React from "react";
import { ChevronDown, Check, Sun, Moon } from "lucide-react";

import type { CompositeType, AvailabilityType } from "../utils/types";
import "./multi-select-composite.css";

interface MultiSelectCompositeProps {
  options: CompositeType[];
  selectedOptions: CompositeType[];
  onChange: (selected: CompositeType[]) => void;
  maxSelections?: number;
  availability?: Record<string, AvailabilityType>;
}

const iconFor = (type?: AvailabilityType) => {
  switch (type) {
    case "day":
      return <Sun size={10} className="availability-icon" />;
    case "night":
      return <Moon size={10} className="availability-icon" />;
    default:
      return null;
  }
};

export default function MultiSelectComposite({
  options,
  selectedOptions,
  onChange,
  maxSelections = 2,
  availability = {}
}: MultiSelectCompositeProps) {
  const [isSelectOpen, setIsSelectOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [isCtrlPressed, setIsCtrlPressed] = useState(false);

  // Format composite name for display (e.g., "day_convection" to "Day Convection")
  const upperCase = (name: string): string => {
    return name
      .split("_")
      .map((segment) =>
        segment.length <= 2
          ? segment.toUpperCase()
          : segment[0].toUpperCase() + segment.slice(1).toLowerCase()
      )
      .join(" ");
  };

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

  // Handle selection toggle
  const toggleOption = (option: CompositeType, e: React.MouseEvent) => {
    // If Ctrl is pressed, handle multi-select
    if (isCtrlPressed || e.ctrlKey) {
      if (selectedOptions.includes(option)) {
        // Only allow deselection if more than one option is selected
        // This ensures at least one option is always selected
        if (selectedOptions.length > 1) {
          onChange(selectedOptions.filter((item) => item !== option));
        }
      } else if (selectedOptions.length < maxSelections) {
        // Add option if under max selections
        onChange([...selectedOptions, option]);
      }
    } else {
      // Single select mode - just select this option if it's not already selected
      if (!selectedOptions.includes(option)) {
        onChange([option]);
      }
    }
  };

  // Close dropdown when clicking outside or pressing Escape
  useEffect(() => {
    if (!isSelectOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsSelectOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault(); // Prevent page scrolling
        event.stopPropagation(); // Prevent event bubbling
        setIsSelectOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isSelectOpen]);

  return (
    <div className="multi-select-composite" ref={dropdownRef}>
      <button
        className="multi-select-button"
        onClick={() => setIsSelectOpen(!isSelectOpen)}
      >
        <span className="selected-content">
          {selectedOptions.map((opt, i) => (
            <span key={opt} className="selected-item">
              <span>{upperCase(opt)}</span>
              {i < selectedOptions.length - 1 && <span className="sep">,</span>}
            </span>
          ))}
        </span>
        <ChevronDown size={14} className="dropdown-icon" />
      </button>

      {isSelectOpen && (
        <div className="multi-select-dropdown">
          {options.map((option) => (
            <div
              key={option}
              className={`multi-select-option ${
                selectedOptions.includes(option) ? "selected" : ""
              }`}
              onClick={(e) => toggleOption(option, e)}
            >
              <span>{upperCase(option)}</span>
              {iconFor(availability[option])}
              <span
                className={
                  selectedOptions.includes(option)
                    ? "check-mark"
                    : "check-mark check-hidden"
                }
              >
                <Check size={14} strokeWidth={2.5} />
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
