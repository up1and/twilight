import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { storage } from "../utils/storage";

const mocks = vi.hoisted(() => ({
  verifyToken: vi.fn()
}));

vi.mock("../utils/api-client", () => ({
  verifyToken: mocks.verifyToken
}));

vi.mock("../views/map", () => ({
  default: () => <div>Map View</div>
}));

vi.mock("../views/login", () => ({
  default: () => <div>Login View</div>
}));

vi.mock("../views/dashboard", () => ({
  default: () => <div>Dashboard View</div>
}));

import App from "../app";

function renderAt(path: string) {
  const memory = memoryLocation({ path, record: true });
  const utils = render(
    <Router hook={memory.hook} searchHook={memory.searchHook}>
      <App />
    </Router>
  );
  return { ...utils, memory };
}

beforeEach(() => {
  localStorage.clear();
  mocks.verifyToken.mockReset();
});

describe("App routing", () => {
  it("renders the login route", () => {
    renderAt("/login");

    expect(screen.getByText("Login View")).toBeInTheDocument();
    expect(mocks.verifyToken).not.toHaveBeenCalled();
  });

  it("renders the map route without authentication", () => {
    renderAt("/");

    expect(screen.getByText("Map View")).toBeInTheDocument();
    expect(mocks.verifyToken).not.toHaveBeenCalled();
  });

  it("redirects to login when no token is stored", async () => {
    const { memory } = renderAt("/dashboard");

    expect(await screen.findByText("Login View")).toBeInTheDocument();
    expect(memory.history).toContain("/login");
    expect(mocks.verifyToken).not.toHaveBeenCalled();
  });

  it("shows a loading state while validating the stored token", () => {
    storage.set("auth-token", "secret");
    mocks.verifyToken.mockReturnValue(new Promise(() => {}));

    const { container } = renderAt("/dashboard");

    expect(container.querySelector(".lucide-loader-circle")).not.toBeNull();
    expect(screen.queryByText("Dashboard View")).not.toBeInTheDocument();
    expect(mocks.verifyToken).toHaveBeenCalledWith("secret");
  });

  it("renders the dashboard for a valid token", async () => {
    storage.set("auth-token", "secret");
    mocks.verifyToken.mockResolvedValue(true);

    renderAt("/dashboard");

    expect(await screen.findByText("Dashboard View")).toBeInTheDocument();
  });

  it("clears an invalid token and redirects to login", async () => {
    storage.set("auth-token", "stale");
    mocks.verifyToken.mockResolvedValue(false);

    const { memory } = renderAt("/dashboard");

    expect(await screen.findByText("Login View")).toBeInTheDocument();
    expect(storage.get("auth-token")).toBeNull();
    expect(memory.history).toContain("/login");
  });
});
