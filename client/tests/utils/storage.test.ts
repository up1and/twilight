import { beforeEach, describe, expect, it } from "vitest";
import { storage } from "../../utils/storage";

describe("storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns null for a missing key", () => {
    expect(storage.get("missing")).toBeNull();
  });

  it("stores and reads a value", () => {
    storage.set("auth-token", "secret");

    expect(storage.get("auth-token")).toBe("secret");
  });

  it("removes the key when value is null", () => {
    localStorage.setItem("auth-token", "secret");

    storage.set("auth-token", null);

    expect(localStorage.getItem("auth-token")).toBeNull();
  });

  it("removes the key when value is an empty string", () => {
    localStorage.setItem("auth-token", "secret");

    storage.set("auth-token", "");

    expect(localStorage.getItem("auth-token")).toBeNull();
  });
});
