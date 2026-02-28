import { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "wouter";
import dayjs from "dayjs";
import {
  fetchTasks,
  fetchRaws,
  fetchLatestComposites
} from "../utils/api-client";
import "./dashboard.css";

// Types
interface Task {
  task_id: string;
  composite: string;
  timestamp: string;
  status: "pending" | "processing" | "completed" | "failed";
  priority: string;
  worker_id?: string;
  created_at: string;
  updated_at: string;
  message?: string;
  duration?: number;
  started?: string;
  ended?: string;
}

interface Raw {
  timestamp: string;
  status: "pending" | "running" | "completed" | "failed";
  files: number;
  size: number;
  started: string | null;
  ended: string | null;
  duration: number | null;
  speed: number | null;
  created: string;
}

const PER_PAGE = 5;

// Helper functions
function formatComposite(str: string | undefined): string {
  if (!str) return "N/A";
  // Special case for ir_clouds -> IR Clouds
  if (str === "ir_clouds") return "IR Clouds";
  return str
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatDateTimeMin(dateStr: string | null | undefined): string {
  if (!dateStr) return "N/A";
  const date = dayjs(dateStr);
  if (!date.isValid()) return "N/A";
  return date.format("YYYY-MM-DD HH:mm");
}

function formatDateTimeSec(dateStr: string | null | undefined): string {
  if (!dateStr) return "N/A";
  const date = dayjs(dateStr);
  if (!date.isValid()) return "N/A";
  return date.format("YYYY-MM-DD HH:mm:ss");
}

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || isNaN(bytes)) return "N/A";
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatNumber(num: number | null | undefined): string | null {
  if (num == null || isNaN(num)) return null;
  return String(num);
}

function getStatusClass(status: string | undefined): string {
  if (!status) return "";
  switch (status) {
    case "pending":
      return "status-pending";
    case "completed":
      return "status-completed";
    case "failed":
      return "status-failed";
    case "running":
    case "processing":
      return "status-running";
    default:
      return "";
  }
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"tasks" | "syncs">("tasks");

  // Tasks state
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskPage, setTaskPage] = useState(1);
  const [taskTotalPages, setTaskTotalPages] = useState(1);
  const [taskStatusFilter, setTaskStatusFilter] = useState("");
  const [taskCompositeFilter, setTaskCompositeFilter] = useState("");
  const [taskPriorityFilter, setTaskPriorityFilter] = useState("");
  const [composites, setComposites] = useState<string[]>([]);

  // Raws state
  const [raws, setRaws] = useState<Raw[]>([]);
  const [rawPage, setRawPage] = useState(1);
  const [rawTotalPages, setRawTotalPages] = useState(1);
  const [rawStatusFilter, setRawStatusFilter] = useState("");

  // Loading state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ref to track if data has been loaded for each tab
  const tasksLoadedRef = useRef(false);
  const rawsLoadedRef = useRef(false);
  const fetchingRef = useRef(false);

  // Fetch composites from API
  const fetchComposites = useCallback(async () => {
    try {
      const data = await fetchLatestComposites();
      const compositeNames = Object.keys(data);
      setComposites(compositeNames);
    } catch {
      // Silently fail - composites filter just won't be available
    }
  }, []);

  // Fetch tasks from API
  const fetchTasksData = useCallback(
    async (
      page: number,
      status: string,
      composite: string,
      priority: string
    ) => {
      if (fetchingRef.current) return;
      fetchingRef.current = true;

      setLoading(true);
      setError(null);
      try {
        const data = await fetchTasks(
          page,
          PER_PAGE,
          status || undefined,
          composite || undefined,
          priority || undefined
        );
        if (!data) {
          throw new Error("Failed to fetch tasks");
        }
        setTasks(data.tasks);
        setTaskPage(data.page);
        setTaskTotalPages(data.pages);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch tasks");
      } finally {
        setLoading(false);
        fetchingRef.current = false;
      }
    },
    []
  );

  // Load composites if not loaded yet
  const loadComposites = useCallback(async () => {
    if (composites.length === 0) {
      await fetchComposites();
    }
  }, [composites.length, fetchComposites]);

  // Fetch raws from API
  const fetchRawsData = useCallback(async (page: number, status: string) => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;

    setLoading(true);
    setError(null);
    try {
      const data = await fetchRaws(page, PER_PAGE, status || undefined);
      if (!data) {
        throw new Error("Failed to fetch raws");
      }

      // Filter by status if specified (client-side filtering for raws)
      let filteredRaws = data.raws;
      if (status) {
        filteredRaws = data.raws.filter((r) => r.status === status);
      }

      setRaws(filteredRaws);
      setRawPage(data.page);
      setRawTotalPages(data.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch raws");
    } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, []);

  // Load tasks when tab is active or filters change
  useEffect(() => {
    if (activeTab !== "tasks") return;

    const shouldLoad = !tasksLoadedRef.current;
    tasksLoadedRef.current = true;

    fetchTasksData(
      taskPage,
      taskStatusFilter,
      taskCompositeFilter,
      taskPriorityFilter
    );

    if (shouldLoad) {
      loadComposites();
    }
  }, [
    activeTab,
    taskPage,
    taskStatusFilter,
    taskCompositeFilter,
    taskPriorityFilter,
    fetchTasksData
  ]);

  // Load raws when tab is active or filters change
  useEffect(() => {
    if (activeTab !== "syncs") return;

    rawsLoadedRef.current = true;

    fetchRawsData(rawPage, rawStatusFilter);
  }, [activeTab, rawPage, rawStatusFilter, fetchRawsData]);

  return (
    <div className="dashboard">
      <div className="container">
        {/* Header */}
        <div className="header-section">
          <h1>Twilight Dashboard</h1>
          <div className="tabs">
            <button
              className={`tab-button ${activeTab === "tasks" ? "active" : ""}`}
              onClick={() => setActiveTab("tasks")}
            >
              Tasks
            </button>
            <button
              className={`tab-button ${activeTab === "syncs" ? "active" : ""}`}
              onClick={() => setActiveTab("syncs")}
            >
              Syncs
            </button>
            <Link className="tab-button" href="/">
              Back
            </Link>
          </div>
        </div>

        {/* Error */}
        {error && <div className="error-banner">{error}</div>}

        {/* Tasks Tab */}
        {activeTab === "tasks" && (
          <div className="tab-content active">
            {/* Filters */}
            <div className="filters">
              <div className="filter-group">
                <span className="filter-label">Composite:</span>
                <select
                  value={taskCompositeFilter}
                  onChange={(e) => setTaskCompositeFilter(e.target.value)}
                >
                  <option value="">All</option>
                  {composites.map((comp) => (
                    <option key={comp} value={comp}>
                      {formatComposite(comp)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="filter-group">
                <span className="filter-label">Priority:</span>
                <select
                  value={taskPriorityFilter}
                  onChange={(e) => setTaskPriorityFilter(e.target.value)}
                >
                  <option value="">All</option>
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                </select>
              </div>
              <div className="filter-group">
                <span className="filter-label">Status:</span>
                <select
                  value={taskStatusFilter}
                  onChange={(e) => setTaskStatusFilter(e.target.value)}
                >
                  <option value="">All</option>
                  <option value="pending">Pending</option>
                  <option value="processing">Processing</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                </select>
              </div>
            </div>

            {/* Cards */}
            <div className="card-list">
              {loading ? (
                <div className="empty-cell">Loading...</div>
              ) : tasks.length === 0 ? (
                <div className="empty-cell">No tasks found</div>
              ) : (
                tasks.map((task) => (
                  <div key={task.task_id} className="data-card">
                    <div className="card-header">
                      <div className="header-left">
                        <span className="title-name">
                          {formatComposite(task.composite)}
                        </span>
                        <span className="timestamp">
                          {formatDateTimeMin(task.timestamp)}
                        </span>
                      </div>
                      <span
                        className={`status-badge ${getStatusClass(task.status)}`}
                      >
                        {task.status?.toUpperCase() || "N/A"}
                      </span>
                    </div>
                    <div className="info-row">
                      <span>
                        <span className="label">Priority:</span>{" "}
                        {task.priority || "N/A"}
                      </span>
                      <span>
                        <span className="label">Created:</span>{" "}
                        {formatDateTimeSec(task.created_at)}
                      </span>
                    </div>
                    <div className="info-row">
                      <span>
                        <span className="label">Worker:</span>{" "}
                        {task.worker_id || "N/A"}
                      </span>
                      <span>
                        <span className="label">Started:</span>{" "}
                        {formatDateTimeSec(task.started)}
                      </span>
                      <span>
                        <span className="label">Duration:</span>{" "}
                        {task.duration != null ? task.duration + "s" : "N/A"}
                      </span>
                    </div>
                    <span className="size-info">{task.task_id}</span>
                  </div>
                ))
              )}
            </div>

            {/* Pagination */}
            <div className="pagination">
              <button
                className="page-button"
                disabled={taskPage === 1}
                onClick={() => setTaskPage(taskPage - 1)}
              >
                Prev
              </button>
              {Array.from({ length: taskTotalPages }, (_, i) => i + 1).map(
                (page) => (
                  <button
                    key={page}
                    className={`page-button ${page === taskPage ? "active" : ""}`}
                    onClick={() => setTaskPage(page)}
                  >
                    {page}
                  </button>
                )
              )}
              <button
                className="page-button"
                disabled={taskPage === taskTotalPages}
                onClick={() => setTaskPage(taskPage + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* Syncs Tab */}
        {activeTab === "syncs" && (
          <div className="tab-content active">
            {/* Filters */}
            <div className="filters">
              <div className="filter-group">
                <span className="filter-label">Status:</span>
                <select
                  value={rawStatusFilter}
                  onChange={(e) => setRawStatusFilter(e.target.value)}
                >
                  <option value="">All</option>
                  <option value="pending">Pending</option>
                  <option value="running">Running</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                </select>
              </div>
            </div>

            {/* Cards */}
            <div className="card-list">
              {loading ? (
                <div className="empty-cell">Loading...</div>
              ) : raws.length === 0 ? (
                <div className="empty-cell">No sync data found</div>
              ) : (
                raws.map((raw) => (
                  <div key={raw.timestamp} className="data-card">
                    <div className="card-header">
                      <div className="header-left">
                        <span className="title-name">Himawari</span>
                        <span className="timestamp">
                          {formatDateTimeMin(raw.timestamp)}
                        </span>
                      </div>
                      <span
                        className={`status-badge ${getStatusClass(raw.status)}`}
                      >
                        {raw.status?.toUpperCase() || "N/A"}
                      </span>
                    </div>
                    <div className="info-row">
                      <span>
                        <span className="label">Started:</span>{" "}
                        {formatDateTimeSec(raw.started)}
                      </span>
                      <span>
                        <span className="label">Created:</span>{" "}
                        {formatDateTimeSec(raw.created)}
                      </span>
                    </div>
                    <div className="info-row">
                      <span>
                        <span className="label">Files:</span>{" "}
                        {formatNumber(raw.files) ?? "N/A"}
                      </span>
                      <span>
                        <span className="label">Speed:</span>{" "}
                        {formatNumber(raw.speed)
                          ? `${formatNumber(raw.speed)} KB/s`
                          : "N/A"}
                      </span>
                      <span>
                        <span className="label">Duration:</span>{" "}
                        {formatNumber(raw.duration)
                          ? `${formatNumber(raw.duration)}s`
                          : "N/A"}
                      </span>
                    </div>
                    <span className="size-info">{formatBytes(raw.size)}</span>
                  </div>
                ))
              )}
            </div>

            {/* Pagination */}
            <div className="pagination">
              <button
                className="page-button"
                disabled={rawPage === 1}
                onClick={() => setRawPage(rawPage - 1)}
              >
                Prev
              </button>
              {Array.from({ length: rawTotalPages }, (_, i) => i + 1).map(
                (page) => (
                  <button
                    key={page}
                    className={`page-button ${page === rawPage ? "active" : ""}`}
                    onClick={() => setRawPage(page)}
                  >
                    {page}
                  </button>
                )
              )}
              <button
                className="page-button"
                disabled={rawPage === rawTotalPages}
                onClick={() => setRawPage(rawPage + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
