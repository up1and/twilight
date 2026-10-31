import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MapLegend from "../../components/map-legend";

const items = [
  { colors: ["#FF6B6B"], label: "Ash" },
  { colors: ["#43ff89", "#eae98f"], label: "Ash (mixed SO2)" }
];

describe("MapLegend", () => {
  it("renders nothing for an empty item list", () => {
    const { container } = render(<MapLegend items={[]} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("starts collapsed and expands on click", () => {
    render(<MapLegend items={items} />);

    expect(screen.queryByText("Ash")).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Show legend"));

    expect(screen.getByText("Ash")).toBeInTheDocument();
    expect(screen.getByText("Ash (mixed SO2)")).toBeInTheDocument();
  });

  it("expands with the keyboard", () => {
    render(<MapLegend items={items} />);

    fireEvent.keyDown(screen.getByLabelText("Show legend"), { key: "Enter" });

    expect(screen.getByText("Ash")).toBeInTheDocument();
  });

  it("collapses from the close control and restores the badge", () => {
    render(<MapLegend items={items} defaultExpanded />);

    fireEvent.click(screen.getByLabelText("Hide legend"));

    expect(screen.queryByText("Ash")).not.toBeInTheDocument();
    expect(screen.getByText("Legend")).toBeInTheDocument();
  });

  it("applies a solid color for single-color items and a gradient for multi-color items", () => {
    const { container } = render(<MapLegend items={items} defaultExpanded />);
    const blocks = container.querySelectorAll<HTMLElement>(".legend-color-block");

    expect(blocks[0].style.backgroundColor).toBe("rgb(255, 107, 107)");
    expect(blocks[1].style.background).toContain("linear-gradient");
    expect(blocks[1].style.background).toContain("rgb(67, 255, 137) 0% 50%");
    expect(blocks[1].style.background).toContain("rgb(234, 233, 143) 50% 100%");
  });
});
