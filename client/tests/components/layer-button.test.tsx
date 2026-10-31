import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LayerButton from "../../components/layer-button";

describe("LayerButton", () => {
  it("opens the dropdown from the layer settings button", () => {
    render(<LayerButton layers={{ "fir-boundary": false }} onToggle={vi.fn()} />);

    expect(screen.queryByText("FIR Boundary")).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Layer Settings"));

    expect(screen.getByText("Layers")).toBeInTheDocument();
    expect(screen.getByText("FIR Boundary")).toBeInTheDocument();
  });

  it("calls onToggle with the layer id", () => {
    const onToggle = vi.fn();
    render(<LayerButton layers={{ "fir-boundary": false }} onToggle={onToggle} />);

    fireEvent.click(screen.getByLabelText("Layer Settings"));
    fireEvent.click(screen.getByText("FIR Boundary"));

    expect(onToggle).toHaveBeenCalledWith("fir-boundary");
  });

  it("shows a check mark when the layer is enabled", () => {
    const { container } = render(
      <LayerButton layers={{ "fir-boundary": true }} onToggle={vi.fn()} />
    );

    fireEvent.click(screen.getByLabelText("Layer Settings"));

    expect(container.querySelector(".lucide-check")).not.toBeNull();
  });

  it("does not show a check mark when the layer is disabled", () => {
    const { container } = render(
      <LayerButton layers={{ "fir-boundary": false }} onToggle={vi.fn()} />
    );

    fireEvent.click(screen.getByLabelText("Layer Settings"));

    expect(container.querySelector(".lucide-check")).toBeNull();
  });

  it("closes on Escape", () => {
    render(<LayerButton layers={{ "fir-boundary": false }} onToggle={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("Layer Settings"));
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByText("FIR Boundary")).not.toBeInTheDocument();
  });

  it("closes when clicking outside", () => {
    render(<LayerButton layers={{ "fir-boundary": false }} onToggle={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("Layer Settings"));
    fireEvent.mouseDown(document.body);

    expect(screen.queryByText("FIR Boundary")).not.toBeInTheDocument();
  });
});
