import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CoordinatesDisplay from "../../components/coordinates-display";

describe("CoordinatesDisplay", () => {
  it("formats positive coordinates as north/east", () => {
    render(<CoordinatesDisplay lat={35.6812} lng={139.7671} />);

    expect(
      screen.getByText('35°40\'52" N | 139°46\'1" E')
    ).toBeInTheDocument();
  });

  it("formats negative coordinates as south/west", () => {
    render(<CoordinatesDisplay lat={-33.5} lng={-74.5} />);

    expect(screen.getByText('33°30\'0" S | 74°30\'0" W')).toBeInTheDocument();
  });

  it("treats zero as north/east", () => {
    render(<CoordinatesDisplay lat={0} lng={0} />);

    expect(screen.getByText('0°0\'0" N | 0°0\'0" E')).toBeInTheDocument();
  });
});
