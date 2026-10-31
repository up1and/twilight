import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

interface CapturedRequest {
  request: Request;
  body?: unknown;
}

const requests: CapturedRequest[] = [];

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

let responder: () => Response = () => jsonResponse({ ok: true });

const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
  const request = input instanceof Request ? input : new Request(input);
  let body: unknown;

  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request
      .clone()
      .json()
      .catch(() => undefined);
  }

  requests.push({ request, body });
  return responder();
});

type ApiModule = typeof import("../../utils/api-client");

let api: ApiModule;
let consoleError: ReturnType<typeof vi.spyOn>;

describe("api-client", () => {
  beforeEach(async () => {
    requests.length = 0;
    responder = () => jsonResponse({ ok: true });
    localStorage.clear();
    consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.stubGlobal("fetch", fetchMock);
    vi.resetModules();
    api = await import("../../utils/api-client");
  });

  afterEach(() => {
    consoleError.mockRestore();
  });

  it("verifies a token via POST /api/auth/verify", async () => {
    responder = () => jsonResponse({ valid: true });

    await expect(api.verifyToken("secret")).resolves.toBe(true);

    expect(requests[0].request.method).toBe("POST");
    expect(requests[0].request.url).toMatch(/\/api\/auth\/verify$/);
    expect(requests[0].body).toEqual({ token: "secret" });
  });

  it("returns false when the token is rejected", async () => {
    responder = () => jsonResponse({ valid: false }, 400);

    await expect(api.verifyToken("wrong")).resolves.toBe(false);
  });

  it("attaches the stored bearer token to requests", async () => {
    localStorage.setItem("auth-token", "stored-token");
    responder = () =>
      jsonResponse({ tasks: [], total: 0, page: 1, per_page: 20, pages: 0 });

    await api.fetchTasks();

    expect(requests[0].request.headers.get("Authorization")).toBe(
      "Bearer stored-token"
    );
  });

  it("builds task query parameters from every filter", async () => {
    responder = () =>
      jsonResponse({ tasks: [], total: 0, page: 2, per_page: 10, pages: 0 });

    await api.fetchTasks(2, 10, "pending", "true_color", "high");

    const url = new URL(requests[0].request.url);
    expect(url.pathname).toBe("/api/tasks");
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("per_page")).toBe("10");
    expect(url.searchParams.get("status")).toBe("pending");
    expect(url.searchParams.get("composite")).toBe("true_color");
    expect(url.searchParams.get("priority")).toBe("high");
  });

  it("returns null when a task request fails", async () => {
    responder = () => new Response("not found", { status: 404 });

    await expect(api.fetchTasks()).resolves.toBeNull();
  });

  it("sends the sync status filter to the API", async () => {
    responder = () =>
      jsonResponse({ syncs: [], total: 0, page: 1, per_page: 20, pages: 0 });

    await api.fetchSyncs(1, 20, "himawari", "completed");

    const url = new URL(requests[0].request.url);
    expect(url.pathname).toBe("/api/syncs");
    expect(url.searchParams.get("source")).toBe("himawari");
    expect(url.searchParams.get("status")).toBe("completed");
  });

  it("parses composite metadata", async () => {
    const payload = {
      true_color: { timestamp: "2025-04-20T04:00:00", availability: "day" }
    };
    responder = () => jsonResponse(payload);

    await expect(api.fetchComposites()).resolves.toEqual(payload);
  });

  it("returns an empty map when composite metadata is unavailable", async () => {
    responder = () => new Response("error", { status: 404 });

    await expect(api.fetchComposites()).resolves.toEqual({});
  });

  it("converts composite names to dashed tile paths for legends", async () => {
    const payload = [{ colors: ["#fff"], label: "Cloud" }];
    responder = () => jsonResponse(payload);

    await expect(api.fetchLegend("true_color")).resolves.toEqual(payload);

    expect(requests[0].request.url).toMatch(
      /\/tiles\/true-color\/legend\.json$/
    );
  });

  it("returns tile JSON and resolves relative tile URLs", async () => {
    const payload = {
      tiles: ["/tiles/true-color/{time}/{z}/{x}/{y}.png"],
      bounds: [70, 0, 150, 55],
      minzoom: 1,
      maxzoom: 10
    };
    responder = () => jsonResponse(payload);

    await expect(api.fetchTileJSON("true_color")).resolves.toEqual({
      ...payload,
      tiles: ["http://localhost:3000/tiles/true-color/{time}/{z}/{x}/{y}.png"]
    });

    expect(requests[0].request.url).toMatch(
      /\/tiles\/true-color\/tile\.json$/
    );
  });

  it("prefixes relative URLs with the configured API base", () => {
    expect(api.resolveApiUrl("/tiles/a.png")).toBe(
      "http://localhost:3000/tiles/a.png"
    );
    expect(api.resolveApiUrl("https://example.com/a.png")).toBe(
      "https://example.com/a.png"
    );
  });

  it("posts snapshot parameters and returns the response", async () => {
    const response = {
      status: "completed",
      download_url: "/snapshots/a.png",
      filename: "a.png"
    };
    responder = () => jsonResponse(response);

    const params = {
      bbox: [100, 20, 140, 50] as [number, number, number, number],
      timestamp: "2025-04-20T04:00:00",
      composite: "true_color",
      timedelta: 30
    };

    await expect(api.createSnapshot(params)).resolves.toEqual(response);

    expect(requests[0].request.method).toBe("POST");
    expect(requests[0].request.url).toMatch(/\/api\/snapshots$/);
    expect(requests[0].body).toEqual(params);
  });

  it("posts task parameters", async () => {
    responder = () =>
      jsonResponse({
        task_id: "task-1",
        status: "pending",
        created: "2025-04-20T04:00:00"
      });

    await api.createTask({
      composite: "ir_clouds",
      timestamp: "2025-04-20T04:00:00",
      priority: "high"
    });

    expect(requests[0].request.method).toBe("POST");
    expect(requests[0].request.url).toMatch(/\/api\/tasks$/);
    expect(requests[0].body).toEqual({
      composite: "ir_clouds",
      timestamp: "2025-04-20T04:00:00",
      priority: "high"
    });
  });
});
