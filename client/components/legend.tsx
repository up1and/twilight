import { useState } from "react";
import { X } from "lucide-react";
import "./legend.css";

export interface LegendItem {
  color: string; // Hex color string, e.g., "#FF6B6B"
  label: string; // Display text, e.g., "Ash"
}

interface LegendProps {
  items: LegendItem[];
  defaultExpanded?: boolean;
}

export default function Legend({
  items,
  defaultExpanded = false
}: LegendProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (!items || items.length === 0) {
    return null;
  }

  return (
    <div className="legend-container">
      {isExpanded ? (
        <div className="legend-wrapper">
          <span
            className="legend-close"
            onClick={() => setIsExpanded(false)}
            role="button"
            tabIndex={0}
            aria-label="Hide legend"
            onKeyDown={(e) => e.key === "Enter" && setIsExpanded(false)}
          >
            <X size={12} />
          </span>
          <div className="legend-panel">
            <div className="legend-list">
              {items.map((item, index) => (
                <div key={index} className="legend-item">
                  <span
                    className="legend-color-block"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="legend-label">{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <span
          className="legend-badge"
          onClick={() => setIsExpanded(true)}
          role="button"
          tabIndex={0}
          aria-label="Show legend"
          onKeyDown={(e) => e.key === "Enter" && setIsExpanded(true)}
        >
          Legend
        </span>
      )}
    </div>
  );
}
