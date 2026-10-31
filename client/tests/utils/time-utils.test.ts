import { describe, expect, it } from "vitest";
import dayjs from "dayjs";
import { roundToNearestTenMinutes } from "../../utils/time-utils";

describe("roundToNearestTenMinutes", () => {
  it("rounds down when minutes are below the midpoint", () => {
    const result = roundToNearestTenMinutes(
      dayjs("2025-04-20T04:04:59.999")
    );

    expect(result.format("YYYY-MM-DD HH:mm:ss")).toBe("2025-04-20 04:00:00");
  });

  it("rounds up when minutes are at or above the midpoint", () => {
    const result = roundToNearestTenMinutes(
      dayjs("2025-04-20T04:05:00.000")
    );

    expect(result.format("YYYY-MM-DD HH:mm:ss")).toBe("2025-04-20 04:10:00");
  });

  it("rolls over to the next hour when rounding 55 minutes", () => {
    const result = roundToNearestTenMinutes(
      dayjs("2025-04-20T04:55:30.000")
    );

    expect(result.format("YYYY-MM-DD HH:mm:ss")).toBe("2025-04-20 05:00:00");
  });

  it("clears seconds and milliseconds even on exact ten-minute marks", () => {
    const result = roundToNearestTenMinutes(
      dayjs("2025-04-20T04:10:42.123")
    );

    expect(result.second()).toBe(0);
    expect(result.millisecond()).toBe(0);
  });

  it("accepts Date and ISO string inputs", () => {
    const fromDate = roundToNearestTenMinutes(new Date(2025, 3, 20, 4, 12));
    const fromString = roundToNearestTenMinutes("2025-04-20T04:12:00");

    expect(fromDate.format("HH:mm")).toBe("04:10");
    expect(fromString.format("HH:mm")).toBe("04:10");
  });
});
