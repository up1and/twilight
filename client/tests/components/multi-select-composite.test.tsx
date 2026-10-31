import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MultiSelectComposite from "../../components/multi-select-composite";
import type { CompositeType } from "../../utils/types";

const options: CompositeType[] = [
  "airmass",
  "ash",
  "day_microphysics",
  "ir_clouds"
];

function renderSelect(
  selectedOptions: CompositeType[] = ["ir_clouds"],
  onChange = vi.fn(),
  extra: { availability?: Record<string, "day" | "night" | "all"> } = {}
) {
  const utils = render(
    <MultiSelectComposite
      options={options}
      selectedOptions={selectedOptions}
      onChange={onChange}
      availability={extra.availability}
    />
  );
  return { ...utils, onChange };
}

function openOption(name: string) {
  const dropdown = document.querySelector(".multi-select-dropdown");
  if (!dropdown) throw new Error("dropdown is not open");
  return within(dropdown as HTMLElement).getByText(name);
}

describe("MultiSelectComposite", () => {
  it("formats selected composite names for display", () => {
    renderSelect(["day_microphysics", "ir_clouds"]);

    expect(screen.getByText("Day Microphysics")).toBeInTheDocument();
    expect(screen.getByText("IR Clouds")).toBeInTheDocument();
  });

  it("shows every formatted option when opened", () => {
    renderSelect();

    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByText("Airmass")).toBeInTheDocument();
    expect(screen.getByText("Ash")).toBeInTheDocument();
    expect(screen.getByText("Day Microphysics")).toBeInTheDocument();
  });

  it("replaces the selection in single-select mode", () => {
    const { onChange } = renderSelect(["ir_clouds"]);

    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(openOption("Ash"));

    expect(onChange).toHaveBeenCalledWith(["ash"]);
  });

  it("does not emit a change when clicking the already selected option", () => {
    const { onChange } = renderSelect(["ir_clouds"]);

    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(openOption("IR Clouds"));

    expect(onChange).not.toHaveBeenCalled();
  });

  it("adds an option when Ctrl-clicking and under the max selections", () => {
    const { onChange } = renderSelect(["ir_clouds"]);

    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(openOption("Ash"), { ctrlKey: true });

    expect(onChange).toHaveBeenCalledWith(["ir_clouds", "ash"]);
  });

  it("stops adding options at the max selections", () => {
    const { onChange } = renderSelect(["ir_clouds", "ash"]);

    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(openOption("Airmass"), { ctrlKey: true });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("removes an option when Ctrl-clicking and more than one is selected", () => {
    const { onChange } = renderSelect(["ir_clouds", "ash"]);

    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(openOption("Ash"), { ctrlKey: true });

    expect(onChange).toHaveBeenCalledWith(["ir_clouds"]);
  });

  it("keeps at least one option selected", () => {
    const { onChange } = renderSelect(["ir_clouds"]);

    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(openOption("IR Clouds"), { ctrlKey: true });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("also honors the tracked Control key state", () => {
    const { onChange } = renderSelect(["ir_clouds"]);

    fireEvent.keyDown(window, { key: "Control" });
    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(openOption("Ash"));

    expect(onChange).toHaveBeenCalledWith(["ir_clouds", "ash"]);
  });

  it("renders availability icons for day and night composites", () => {
    const { container } = renderSelect(["ir_clouds"], vi.fn(), {
      availability: { airmass: "day", ash: "night" }
    });

    fireEvent.click(screen.getByRole("button"));

    expect(container.querySelector(".lucide-sun")).not.toBeNull();
    expect(container.querySelector(".lucide-moon")).not.toBeNull();
  });

  it("marks selected options and hides checks for unselected ones", () => {
    const { container } = renderSelect(["ir_clouds"]);

    fireEvent.click(screen.getByRole("button"));

    const checkMarks = container.querySelectorAll(".check-mark");
    expect(checkMarks).toHaveLength(options.length);
    expect(
      container.querySelectorAll(".check-mark.check-hidden")
    ).toHaveLength(options.length - 1);
  });

  it("closes on Escape", () => {
    renderSelect();

    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Airmass")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByText("Airmass")).not.toBeInTheDocument();
  });

  it("closes when clicking outside", () => {
    renderSelect();

    fireEvent.click(screen.getByRole("button"));
    fireEvent.mouseDown(document.body);

    expect(screen.queryByText("Airmass")).not.toBeInTheDocument();
  });
});
