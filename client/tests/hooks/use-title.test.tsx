import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useTitle } from "../../hooks/use-title";

describe("useTitle", () => {
  it("sets the document title on mount", () => {
    document.title = "Original";
    renderHook(() => useTitle("Login"));
    expect(document.title).toBe("Login");
  });

  it("updates the document title when the title changes", () => {
    document.title = "Original";
    const { rerender } = renderHook(({ title }) => useTitle(title), {
      initialProps: { title: "First" }
    });

    expect(document.title).toBe("First");

    rerender({ title: "Second" });
    expect(document.title).toBe("Second");
  });

  it("restores the previous title on unmount", () => {
    document.title = "Original";
    const { unmount } = renderHook(() => useTitle("Dashboard"));

    expect(document.title).toBe("Dashboard");

    unmount();
    expect(document.title).toBe("Original");
  });
});
