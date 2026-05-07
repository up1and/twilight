import { useState } from "react";
import { X } from "lucide-react";
import "./map-legend.css";

export interface MapLegendItem {
  colors: string[]; // Array of hex colors, vertically split in the block
  label: string;
}

function getColorStyle(colors: string[]): React.CSSProperties {
  const n = colors.length;
  if (n === 0) return {};
  if (n === 1) return { backgroundColor: colors[0] };

  // Multiple colors: vertical gradient with hard stops (left-to-right bands)
  const parts = colors.map((c, i) => {
    const start = (i / n) * 100;
    const end = ((i + 1) / n) * 100;
    return `${c} ${start}%, ${c} ${end}%`;
  });
  return {
    background: `linear-gradient(to right, ${parts.join(", ")})`
  };
}

interface MapLegendProps {
  items: MapLegendItem[];
  defaultExpanded?: boolean;
}

export default function MapLegend({
  items,
  defaultExpanded = false
}: MapLegendProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (!items || items.length === 0) {
    return null;
  }

  return (
    <div className="map-legend-container">
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
                    style={getColorStyle(item.colors)}
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
