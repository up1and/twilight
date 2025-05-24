import { useState, useRef, useEffect } from "react";
import type React from "react";

import type { CompositeType } from "../utils/types";
import "./multi-select-composite.css";

interface MultiSelectCompositeProps {
  options: CompositeType[];
  selectedOptions: CompositeType[];
  onChange: (selected: CompositeType[]) => void;
  maxSelections?: number;
}

// Types of formatted names for display in the UI
type DisplayNameType = string;

// Stores a mapping of snake_case names to display names
interface CompositeMapping {
  value: CompositeType;
  display: DisplayNameType;
}

export default function MultiSelectComposite({
  options,
  selectedOptions,
  onChange,
  maxSelections = 2,
}: MultiSelectCompositeProps) {
  const [isOpen, setIsOpen] = useState(false);
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

  options.map((option) => ({
    value: option,
    display: upperCase(option),
  })) as CompositeMapping[];

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

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Format the display text for the button
  const getDisplayText = () => {
    if (selectedOptions.length === 0) {
      return "Select layers";
    } else if (selectedOptions.length === 1) {
      return upperCase(selectedOptions[0]);
    } else {
      // Show both selected options with comma separator
      return `${upperCase(selectedOptions[0])}, ${upperCase(
        selectedOptions[1]
      )}`;
    }
  };

  return (
    <div className="multi-select-composite" ref={dropdownRef}>
      <button
        className="multi-select-button"
        onClick={() => setIsOpen(!isOpen)}
      >
        {getDisplayText()}
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
          className="dropdown-icon"
        >
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>

      {isOpen && (
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
              {selectedOptions.includes(option) && (
                <span className="check-mark">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
