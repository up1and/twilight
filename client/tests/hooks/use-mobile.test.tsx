import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useIsMobile } from "../../hooks/use-mobile";

type ChangeListener = (event: MediaQueryListEvent) => void;

function setViewportWidth(width: number) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width
  });
}

function installMatchMedia() {
  const listeners = new Set<ChangeListener>();
  const mql = {
    matches: false,
    media: "",
    onchange: null,
    addEventListener: vi.fn((_type: string, listener: ChangeListener) => {
      listeners.add(listener);
    }),
    removeEventListener: vi.fn((_type: string, listener: ChangeListener) => {
      listeners.delete(listener);
    }),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn()
  };

  const matchMedia = vi.fn(() => mql);
  vi.stubGlobal("matchMedia", matchMedia);

  return { mql, listeners, matchMedia };
}

afterEach(() => {
  setViewportWidth(1024);
});

describe("useIsMobile", () => {
  it("reports mobile when the viewport is narrower than 768px", () => {
    setViewportWidth(375);
    const { matchMedia } = installMatchMedia();

    const { result } = renderHook(() => useIsMobile());

    expect(matchMedia).toHaveBeenCalledWith("(max-width: 767px)");
    expect(result.current).toBe(true);
  });

  it("reports desktop at the breakpoint width", () => {
    setViewportWidth(768);
    installMatchMedia();

    const { result } = renderHook(() => useIsMobile());

    expect(result.current).toBe(false);
  });

  it("updates when the media query fires a change event", () => {
    setViewportWidth(1024);
    const { listeners } = installMatchMedia();

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    setViewportWidth(500);
    act(() => {
      listeners.forEach((listener) =>
        listener({} as MediaQueryListEvent)
      );
    });

    expect(result.current).toBe(true);
  });

  it("removes its change listener on unmount", () => {
    setViewportWidth(1024);
    const { mql } = installMatchMedia();

    const { unmount } = renderHook(() => useIsMobile());
    unmount();

    expect(mql.removeEventListener).toHaveBeenCalledWith(
      "change",
      expect.any(Function)
    );
  });
});
