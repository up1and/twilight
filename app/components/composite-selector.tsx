import type { CompositeType } from "../utils/types";
import "./composite-selector.css";

interface CompositeSelectorProps {
  value: CompositeType;
  onChange: (value: CompositeType) => void;
}

export default function CompositeSelector({
  value,
  onChange,
}: CompositeSelectorProps) {
  const compositeOptions: CompositeType[] = [
    "True Color",
    "IR Clouds",
    "Ash",
    "Water Vapor",
    "Dust",
  ];

  // Use native select element to match the lookback selector
  return (
    <div className="composite-selector">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as CompositeType)}
        className="composite-select"
      >
        {compositeOptions.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}
