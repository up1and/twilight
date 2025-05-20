import type { CompositeType } from "../utils/types";
import "./composite-selector.css";

interface CompositeSelectorProps {
  value: CompositeType;
  onChange: (value: CompositeType) => void;
  composites: CompositeType[]; // Available options from parent
}

export default function CompositeSelector({
  value,
  onChange,
  composites,
}: CompositeSelectorProps) {
  // Use native select element to match the lookback selector
  return (
    <div className="composite-selector">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as CompositeType)}
        className="composite-select"
      >
        {composites.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}
