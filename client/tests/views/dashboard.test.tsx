import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { storage } from "../../utils/storage";
import type { Sync, Task } from "../../utils/types";

const mocks = vi.hoisted(() => ({
  fetchTasks: vi.fn(),
  fetchSyncs: vi.fn(),
  fetchComposites: vi.fn(),
  createTask: vi.fn(),
  fetchProfile: vi.fn(),
  setLocation: vi.fn()
}));

vi.mock("../../utils/api-client", () => ({
  fetchTasks: mocks.fetchTasks,
  fetchSyncs: mocks.fetchSyncs,
  fetchComposites: mocks.fetchComposites,
  createTask: mocks.createTask,
  fetchProfile: mocks.fetchProfile
}));

vi.mock("wouter", () => ({
  useLocation: () => ["/dashboard", mocks.setLocation],
  Link: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  )
}));

import Dashboard from "../../views/dashboard";

const tasksResponse = {
  tasks: [] as Task[],
  total: 0,
  page: 1,
  per_page: 10,
  pages: 1
};

const syncsResponse = {
  syncs: [] as Sync[],
  total: 0,
  page: 1,
  per_page: 10,
  pages: 1
};

const task: Task = {
  task_id: "t1",
  composite: "true_color",
  timestamp: "2025-04-20T04:00:00",
  status: "completed",
  priority: "high",
  worker_id: "worker-1",
  created: "2025-04-20T04:05:00",
  started: "2025-04-20T04:06:00",
  duration: 42
};

const sync: Sync = {
  timestamp: "2025-04-20T04:00:00",
  source: "himawari",
  status: "completed",
  files: 3,
  size: 2048,
  started: "2025-04-20T04:01:00",
  ended: "2025-04-20T04:02:00",
  duration: 60,
  speed: 512,
  created: "2025-04-20T04:00:30"
};

beforeEach(() => {
  localStorage.clear();
  mocks.fetchTasks.mockReset();
  mocks.fetchSyncs.mockReset();
  mocks.fetchComposites.mockReset();
  mocks.createTask.mockReset();
  mocks.fetchProfile.mockReset();
  mocks.setLocation.mockReset();

  mocks.fetchTasks.mockResolvedValue(tasksResponse);
  mocks.fetchSyncs.mockResolvedValue(syncsResponse);
  mocks.fetchComposites.mockResolvedValue({});
});

describe("Dashboard", () => {
  it("loads the first page of tasks and renders the empty state", async () => {
    render(<Dashboard />);

    expect(await screen.findByText("No tasks found")).toBeInTheDocument();
    expect(mocks.fetchTasks).toHaveBeenCalledWith(
      1,
      10,
      undefined,
      undefined,
      undefined
    );
    expect(document.title).toBe("Dashboard");
  });

  it("renders task details and opens the profile modal", async () => {
    mocks.fetchTasks.mockResolvedValue({ ...tasksResponse, tasks: [task] });
    mocks.fetchProfile.mockResolvedValue({
      task_id: "t1",
      tasks: [{ key: "load", duration: 1.5 }],
      resources: []
    });

    render(<Dashboard />);

    expect(await screen.findByText("True Color")).toBeInTheDocument();
    const card = document.querySelector(".data-card")!;
    expect(card).toHaveTextContent("Priority: high");
    expect(card).toHaveTextContent("t1");

    const badge = document.querySelector(".status-badge")!;
    expect(badge).toHaveTextContent("COMPLETED");
    fireEvent.click(badge);

    expect(mocks.fetchProfile).toHaveBeenCalledWith("t1");
    expect(await screen.findByText("Profile: t1")).toBeInTheDocument();
    expect(screen.getByText("No resource data")).toBeInTheDocument();
    expect(screen.getByText("load")).toBeInTheDocument();
    expect(screen.getByText("1.500s")).toBeInTheDocument();
  });

  it("switches to the syncs tab", async () => {
    mocks.fetchSyncs.mockResolvedValue({
      ...syncsResponse,
      syncs: [sync]
    });

    render(<Dashboard />);
    await screen.findByText("No tasks found");

    fireEvent.click(screen.getByRole("button", { name: "Syncs" }));

    expect(await screen.findByText("himawari")).toBeInTheDocument();
    expect(mocks.fetchSyncs).toHaveBeenCalledWith(1, 10, undefined);
    expect(screen.getByText("2 KB")).toBeInTheDocument();
  });

  it("logs out by clearing the token and navigating home", async () => {
    storage.set("auth-token", "secret");

    render(<Dashboard />);
    await screen.findByText("No tasks found");

    fireEvent.click(screen.getByRole("button", { name: "Logout" }));

    expect(storage.get("auth-token")).toBeNull();
    expect(mocks.setLocation).toHaveBeenCalledWith("/");
  });

  it("lists the available composites in the task filter", async () => {
    mocks.fetchComposites.mockResolvedValue({
      ir_clouds: { timestamp: "2025-04-20T04:00:00", availability: "all" },
      true_color: { timestamp: "2025-04-20T04:00:00", availability: "day" }
    });

    render(<Dashboard />);

    expect(
      await screen.findByRole("option", { name: "True Color" })
    ).toBeInTheDocument();
  });

  it("creates a task with a timestamp rounded down to ten minutes", async () => {
    mocks.createTask.mockResolvedValue({
      task_id: "t2",
      status: "pending",
      created: "2025-04-20T04:12:00"
    });

    const { container } = render(<Dashboard />);
    await screen.findByText("No tasks found");

    fireEvent.click(screen.getByRole("button", { name: "+ Add Task" }));
    expect(screen.getByText("Add New Task")).toBeInTheDocument();

    const timestampInput = container.querySelector<HTMLInputElement>(
      'input[type="datetime-local"]'
    )!;
    fireEvent.change(timestampInput, {
      target: { value: "2025-04-20T04:12" }
    });
    expect(timestampInput).toHaveValue("2025-04-20T04:10");

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(mocks.createTask).toHaveBeenCalledWith({
        composite: "ir_clouds",
        priority: "normal",
        timestamp: new Date("2025-04-20T04:10").toISOString()
      })
    );
    await waitFor(() =>
      expect(screen.queryByText("Add New Task")).not.toBeInTheDocument()
    );
  });

  it("does not submit the add-task form without a timestamp", async () => {
    render(<Dashboard />);
    await screen.findByText("No tasks found");

    fireEvent.click(screen.getByRole("button", { name: "+ Add Task" }));
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(mocks.createTask).not.toHaveBeenCalled();
  });
});
