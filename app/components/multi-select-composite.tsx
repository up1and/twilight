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

export default function MultiSelectComposite({
  options,
  selectedOptions,
  onChange,
  maxSelections = 2,
}: MultiSelectCompositeProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
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
      return selectedOptions[0];
    } else {
      // Show both selected options with comma separator
      return `${selectedOptions[0]}, ${selectedOptions[1]}`;
    }
  };

  return (
    <div className="multi-select-composite" ref={dropdownRef}>
      <button
        className="multi-select-button"
        onClick={() => setIsOpen(!isOpen)}
      >
        {getDisplayText()}
        <span className="dropdown-arrow">▼</span>
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
              <span>{option}</span>
              {selectedOptions.includes(option) && (
                <span className="check-mark">✓</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
