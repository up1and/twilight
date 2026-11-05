import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import SnapshotButton from "../../components/snapshot-button";

dayjs.extend(utc);

const mocks = vi.hoisted(() => ({
  createSnapshot: vi.fn(),
  getSnapshotJob: vi.fn(),
  get: vi.fn()
}));

vi.mock("../../utils/api-client", () => ({
  createSnapshot: mocks.createSnapshot,
  getSnapshotJob: mocks.getSnapshotJob,
  apiClient: { get: mocks.get },
  resolveApiUrl: (path: string) => `http://api.test${path}`
}));

const bbox: [number, number, number, number] = [100, 20, 140, 50];
const selectedTime = dayjs.utc("2025-04-20T04:00:00");

let consoleError: ReturnType<typeof vi.spyOn>;
let clickSpy: ReturnType<typeof vi.spyOn>;
let createObjectURL: ReturnType<typeof vi.fn>;
let revokeObjectURL: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mocks.createSnapshot.mockReset();
  mocks.getSnapshotJob.mockReset();
  mocks.get.mockReset();
  consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
  clickSpy = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  createObjectURL = vi.fn(() => "blob:mock");
  revokeObjectURL = vi.fn();
  Object.defineProperty(window.URL, "createObjectURL", {
    configurable: true,
    writable: true,
    value: createObjectURL
  });
  Object.defineProperty(window.URL, "revokeObjectURL", {
    configurable: true,
    writable: true,
    value: revokeObjectURL
  });
});

afterEach(() => {
  consoleError.mockRestore();
  clickSpy.mockRestore();
});

describe("SnapshotButton", () => {
  it("does nothing when the map bounds are unavailable", () => {
    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={null}
        zoom={6}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    expect(mocks.createSnapshot).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalledWith("Map bounds not available");
  });

  it("does nothing when the map zoom is unavailable", () => {
    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={null}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    expect(mocks.createSnapshot).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalledWith("Map zoom not available");
  });

  it("snapshots the selected composite with a UTC timestamp", async () => {
    mocks.createSnapshot.mockResolvedValue({ status: "pending", job_id: "job-1" });
    mocks.getSnapshotJob.mockResolvedValue({ status: "pending", job_id: "job-1" });

    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(mocks.createSnapshot).toHaveBeenCalledTimes(1));
    expect(mocks.createSnapshot).toHaveBeenCalledWith({
      bbox,
      timestamp: "2025-04-20T04:00:00+0000",
      composite: "true_color",
      zoom: 6
    });
  });

  it("requests one snapshot per composite", async () => {
    // Each render completes immediately so the loop moves on to the next one.
    mocks.createSnapshot.mockResolvedValue({
      status: "completed",
      job_id: "job-1",
      download_url: "/files/a.png"
    });
    mocks.getSnapshotJob.mockResolvedValue({ status: "completed", job_id: "job-1" });
    mocks.get.mockResolvedValue({
      blob: async () => new Blob(["image"], { type: "image/png" })
    });

    render(
      <SnapshotButton
        composites={["true_color", "ir_clouds"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(mocks.createSnapshot).toHaveBeenCalledTimes(2));
    expect(mocks.createSnapshot).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ composite: "true_color" })
    );
    expect(mocks.createSnapshot).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ composite: "ir_clouds" })
    );
  });

  it("downloads a completed snapshot and cleans up the object URL", async () => {
    mocks.createSnapshot.mockResolvedValue({
      status: "completed",
      download_url: "/files/snapshot.png",
      filename: "snapshot.png"
    });
    mocks.get.mockResolvedValue({
      blob: async () => new Blob(["image"], { type: "image/png" })
    });

    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(clickSpy).toHaveBeenCalledTimes(1));
    expect(mocks.get).toHaveBeenCalledWith(
      "http://api.test/files/snapshot.png"
    );
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock");
    expect(document.querySelector("a[download]")).toBeNull();
  });

  it("does not download when the snapshot did not complete", async () => {
    mocks.createSnapshot.mockResolvedValue({
      status: "failed",
      message: "render failed"
    });

    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(mocks.createSnapshot).toHaveBeenCalled());
    expect(mocks.get).not.toHaveBeenCalled();
    expect(clickSpy).not.toHaveBeenCalled();
  });

  it("shows the video icon while Ctrl is held and forwards the timedelta", async () => {
    mocks.createSnapshot.mockResolvedValue({ status: "pending", job_id: "job-1" });
    mocks.getSnapshotJob.mockResolvedValue({ status: "pending", job_id: "job-1" });

    const { container } = render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
        timedelta={60}
      />
    );

    expect(container.querySelector(".lucide-camera")).not.toBeNull();

    fireEvent.keyDown(window, { key: "Control" });
    expect(container.querySelector(".lucide-video")).not.toBeNull();

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(mocks.createSnapshot).toHaveBeenCalled());
    expect(mocks.createSnapshot).toHaveBeenCalledWith(
      expect.objectContaining({ timedelta: 60 })
    );
  });

  it("omits the timedelta when Ctrl is not held", async () => {
    mocks.createSnapshot.mockResolvedValue({ status: "pending", job_id: "job-1" });
    mocks.getSnapshotJob.mockResolvedValue({ status: "pending", job_id: "job-1" });

    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
        timedelta={60}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(mocks.createSnapshot).toHaveBeenCalled());
    const params = mocks.createSnapshot.mock.calls[0][0];
    expect(params).not.toHaveProperty("timedelta");
  });

  it("polls a queued job until the render completes", async () => {
    mocks.createSnapshot.mockResolvedValue({
      status: "pending",
      job_id: "job-1"
    });
    // queued -> running -> completed; the first poll fires as soon as the
    // button mounts, so keep the sequence strictly ordered.
    mocks.getSnapshotJob
      .mockResolvedValueOnce({ status: "pending", job_id: "job-1" })
      .mockResolvedValueOnce({ status: "running", job_id: "job-1" })
      .mockResolvedValue({
        status: "completed",
        job_id: "job-1",
        download_url: "/files/done.png"
      });
    mocks.get.mockResolvedValue({
      blob: async () => new Blob(["image"], { type: "image/png" })
    });

    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(clickSpy).toHaveBeenCalledTimes(1), {
      timeout: 10000
    });
    expect(mocks.getSnapshotJob.mock.calls.length).toBeGreaterThanOrEqual(3);
    expect(mocks.getSnapshotJob).toHaveBeenCalledWith("job-1");
    expect(mocks.get).toHaveBeenCalledWith("http://api.test/files/done.png");
  }, 15000);

  it("stops polling when the queued job fails", async () => {
    mocks.createSnapshot.mockResolvedValue({
      status: "pending",
      job_id: "job-2"
    });
    mocks.getSnapshotJob.mockResolvedValue({
      status: "failed",
      job_id: "job-2",
      message: "render failed"
    });

    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(mocks.getSnapshotJob).toHaveBeenCalledTimes(1), {
      timeout: 10000
    });
    expect(mocks.get).not.toHaveBeenCalled();
    expect(clickSpy).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalledWith(
      "Failed to create snapshot for",
      "true_color",
      "render failed"
    );
  }, 15000);

  it("does not poll when the render finished synchronously", async () => {
    mocks.createSnapshot.mockResolvedValue({
      status: "completed",
      download_url: "/files/sync.png",
      filename: "sync.png"
    });
    mocks.get.mockResolvedValue({
      blob: async () => new Blob(["image"], { type: "image/png" })
    });

    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(clickSpy).toHaveBeenCalledTimes(1));
    expect(mocks.getSnapshotJob).not.toHaveBeenCalled();
  });

  it("resets the loading state when the request fails", async () => {
    mocks.createSnapshot.mockRejectedValue(new Error("network down"));

    render(
      <SnapshotButton
        composites={["true_color"]}
        selectedTime={selectedTime}
        bbox={bbox}
        zoom={6}
      />
    );

    const button = screen.getByRole("button");
    fireEvent.click(button);

    await waitFor(() => expect(button).not.toBeDisabled());
    expect(consoleError).toHaveBeenCalledWith(
      "Snapshot error:",
      expect.any(Error)
    );
  });
});
