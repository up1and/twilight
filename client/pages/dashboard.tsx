import { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "wouter";
import dayjs from "dayjs";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from "chart.js";
import { Line } from "react-chartjs-2";

import {
  fetchTasks,
  fetchSyncs,
  fetchLatestComposites,
  createTask,
  fetchProfile
} from "../utils/api-client";
import type { Task, Sync, Profile } from "../utils/types";
import "./dashboard.css";

interface TaskData {
  key: string;
  duration: number;
}

interface ResourceData {
  time: number;
  memory: number;
  cpu_percent: number;
}

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

const FilterGroup = ({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: { label: string; value: string }[];
  onChange: (v: string) => void;
}) => (
  <div className="filter-group">
    <span className="filter-label">{label}:</span>
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">All</option>
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  </div>
);

const Pagination = ({
  current,
  total,
  onChange
}: {
  current: number;
  total: number;
  onChange: (p: number) => void;
}) => (
  <div className="pagination">
    <button
      className="page-button"
      disabled={current <= 1}
      onClick={() => onChange(current - 1)}
    >
      Prev
    </button>
    {Array.from({ length: total }, (_, i) => i + 1).map((p) => (
      <button
        key={p}
        className={`page-button ${p === current ? "active" : ""}`}
        onClick={() => onChange(p)}
      >
        {p}
      </button>
    ))}
    <button
      className="page-button"
      disabled={current >= total}
      onClick={() => onChange(current + 1)}
    >
      Next
    </button>
  </div>
);

const DataList = ({
  length,
  emptyText,
  children
}: {
  length: number;
  emptyText: string;
  children: React.ReactNode;
}) => (
  <div className="card-list">
    {length === 0 ? <div className="empty-cell">{emptyText}</div> : children}
  </div>
);

const TaskCard = ({
  task,
  onViewProfile
}: {
  task: Task;
  onViewProfile?: (taskId: string) => void;
}) => (
  <div className="data-card">
    <div className="card-header">
      <div className="header-left">
        <span className="title-name">{formatComposite(task.composite)}</span>
        <span className="timestamp">{formatDateTimeMin(task.timestamp)}</span>
      </div>
      {task.status === "completed" ? (
        <span
          className={`status-badge status-${task.status} clickable`}
          onClick={() => onViewProfile?.(task.task_id)}
        >
          {task.status?.toUpperCase()}
        </span>
      ) : (
        <span className={`status-badge status-${task.status}`}>
          {task.status?.toUpperCase()}
        </span>
      )}
    </div>
    <div className="info-row">
      <span>
        <span className="label">Priority:</span> {task.priority}
      </span>
      <span>
        <span className="label">Created:</span>{" "}
        {formatDateTimeSec(task.created)}
      </span>
    </div>
    <div className="info-row">
      <span>
        <span className="label">Worker:</span> {task.worker_id || "N/A"}
      </span>
      <span>
        <span className="label">Started:</span>{" "}
        {formatDateTimeSec(task.started)}
      </span>
      <span>
        <span className="label">Duration:</span>{" "}
        {task.duration ? `${task.duration}s` : "N/A"}
      </span>
    </div>
    {task.message && <div className="error-message">Error: {task.message}</div>}
    <span className="size-info">{task.task_id}</span>
  </div>
);

const SyncCard = ({ sync }: { sync: Sync }) => (
  <div className="data-card">
    <div className="card-header">
      <div className="header-left">
        <span className="title-name">{sync.source}</span>
        <span className="timestamp">{formatDateTimeMin(sync.timestamp)}</span>
      </div>
      <span className={`status-badge status-${sync.status}`}>
        {sync.status?.toUpperCase()}
      </span>
    </div>
    <div className="info-row">
      <span>
        <span className="label">Created:</span>{" "}
        {formatDateTimeSec(sync.created)}
      </span>
      <span>
        <span className="label">Started:</span>{" "}
        {formatDateTimeSec(sync.started)}
      </span>
    </div>
    <div className="info-row">
      <span>
        <span className="label">Files:</span> {sync.files}
      </span>
      <span>
        <span className="label">Speed:</span>{" "}
        {sync.speed ? `${sync.speed} KB/s` : "N/A"}
      </span>
      <span>
        <span className="label">Duration:</span>{" "}
        {sync.duration ? `${sync.duration}s` : "N/A"}
      </span>
    </div>
    <span className="size-info">{formatBytes(sync.size)}</span>
  </div>
);

const AddTaskModal = ({
  show,
  onClose,
  composites,
  onCreated
}: {
  show: boolean;
  onClose: () => void;
  composites: string[];
  onCreated: () => void;
}) => {
  const [form, setForm] = useState({
    composite: "ir_clouds",
    timestamp: "",
    priority: "normal"
  });
  const [submitting, setSubmitting] = useState(false);

  if (!show) return null;

  const handleTimeChange = (val: string) => {
    if (!val) {
      setForm({ ...form, timestamp: "" });
      return;
    }

    const date = new Date(val);

    // Prevent selecting future dates
    if (date > new Date()) return;

    // Round down to the nearest 10-minute increment
    date.setMinutes(Math.floor(date.getMinutes() / 10) * 10);
    date.setSeconds(0);
    date.setMilliseconds(0);

    // Format back to 'YYYY-MM-DDTHH:mm' for datetime-local input
    const localTimestamp = new Date(
      date.getTime() - date.getTimezoneOffset() * 60000
    )
      .toISOString()
      .slice(0, 16);

    setForm({ ...form, timestamp: localTimestamp });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.timestamp || submitting) return;
    setSubmitting(true);
    try {
      const result = await createTask({
        ...form,
        timestamp: new Date(form.timestamp).toISOString()
      });
      if (result) {
        onCreated();
        onClose();
        setForm({ composite: "ir_clouds", timestamp: "", priority: "normal" });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">Add New Task</div>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Composite</label>
            <select
              className="form-input"
              value={form.composite}
              onChange={(e) => setForm({ ...form, composite: e.target.value })}
            >
              {composites.map((c) => (
                <option key={c} value={c}>
                  {formatComposite(c)}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Timestamp</label>
            <input
              type="datetime-local"
              className="form-input"
              value={form.timestamp}
              onChange={(e) => handleTimeChange(e.target.value)}
              max={dayjs().format("YYYY-MM-DDTHH:mm")}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Priority</label>
            <select
              className="form-input"
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
            >
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
            </select>
          </div>
          <div className="modal-actions">
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="add-button" disabled={submitting}>
              {submitting ? "Submitting..." : "Submit"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const ResourceChart = ({ data }: { data: ResourceData[] }) => {
  if (!data || data.length === 0)
    return <div className="empty-cell">No resource data</div>;

  const labels = data.map((_, i) => `${i}`);
  const memData = data.map((r) => r.memory);
  const cpuData = data.map((r) => r.cpu_percent);

  const chartData = {
    labels,
    datasets: [
      {
        label: "CPU",
        data: cpuData,
        borderColor: "#000",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
        yAxisID: "y"
      },
      {
        label: "MEM",
        data: memData,
        borderColor: "#777",
        backgroundColor: "rgba(119, 119, 119, 0.2)",
        borderWidth: 1,
        pointRadius: 0,
        tension: 0.3,
        fill: true,
        yAxisID: "y1"
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index" as const,
      intersect: false
    },
    plugins: {
      legend: {
        position: "top" as const
      },
      tooltip: {
        callbacks: {
          title: () => "",
          label: (context: any) => {
            const label = context.dataset.label || "";
            const value = context.raw;
            if (label === "CPU") {
              return `${label}: ${value.toFixed(1)}%`;
            }
            return `${label}: ${value.toFixed(1)} MB`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: {
          offset: false
        },
        ticks: {
          callback: function (index: any) {
            return index % 5 === 0 ? index : null;
          }
        }
      },
      y: {
        type: "linear" as const,
        position: "right" as const,
        title: {
          display: true,
          text: "CPU"
        }
      },
      y1: {
        type: "linear" as const,
        position: "left" as const,
        grid: {
          drawOnChartArea: false
        },
        title: {
          display: true,
          text: "MEM"
        }
      }
    }
  };

  return (
    <div style={{ height: "200px" }}>
      <Line data={chartData} options={options} />
    </div>
  );
};

const TaskList = ({ data }: { data: TaskData[] }) => {
  if (!data || data.length === 0)
    return <div className="empty-cell">No task data</div>;

  const sortedTasks = [...data]
    .sort((a, b) => b.duration - a.duration)
    .slice(0, 10);

  return (
    <div className="trace-list">
      {sortedTasks.map((task, idx) => (
        <div className="trace-item" key={idx}>
          <span className="trace-key" title={task.key}>
            {task.key}
          </span>
          <b>{task.duration.toFixed(3)}s</b>
        </div>
      ))}
    </div>
  );
};

const ProfileModal = ({
  show,
  onClose,
  taskId
}: {
  show: boolean;
  onClose: () => void;
  taskId: string | null;
}) => {
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    if (show && taskId) {
      fetchProfile(taskId).then((data) => {
        setProfile(data);
      });
    }
  }, [show, taskId]);

  if (!show) return null;

  return (
    <div className="modal" onClick={onClose}>
      <div
        className="modal-content modal-wide"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">Profile: {taskId}</div>
        {profile ? (
          <div className="profile">
            <div className="profile-section">
              <ResourceChart data={profile.resources || []} />
            </div>

            <div className="profile-section">
              <div className="profile-section-title">Execution Trace</div>
              <TaskList data={profile.tasks || []} />
            </div>
          </div>
        ) : (
          <div className="empty-cell">No profile data available</div>
        )}
        <div className="modal-actions">
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"tasks" | "syncs">("tasks");
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  // Task View State
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskParams, setTaskParams] = useState({
    page: 1,
    status: "",
    composite: "",
    priority: ""
  });
  const [taskTotalPages, setTaskTotalPages] = useState(1);

  // Sync View State
  const [syncs, setSyncs] = useState<Sync[]>([]);
  const [syncParams, setSyncParams] = useState({ page: 1, status: "" });
  const [syncTotalPages, setSyncTotalPages] = useState(1);

  // Dictionary State
  const [composites, setComposites] = useState<string[]>([]);
  const fetchingRef = useRef(false);
  const compositesLoadedRef = useRef(false);

  const handleViewProfile = useCallback((taskId: string) => {
    setSelectedTaskId(taskId);
    setShowProfile(true);
  }, []);

  const loadTasks = useCallback(async () => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    try {
      const data = await fetchTasks(
        taskParams.page,
        10,
        taskParams.status || undefined,
        taskParams.composite || undefined,
        taskParams.priority || undefined
      );
      if (data) {
        setTasks(data.tasks || []);
        setTaskTotalPages(data.pages || 1);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      fetchingRef.current = false;
    }
  }, [taskParams]);

  const loadSyncs = useCallback(async () => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    try {
      const data = await fetchSyncs(
        syncParams.page,
        10,
        syncParams.status || undefined
      );
      if (data) {
        const items = data.syncs || [];
        // Filtering locally if status is provided, otherwise using data.syncs
        setSyncs(
          syncParams.status
            ? items.filter((item: any) => item.status === syncParams.status)
            : items
        );
        setSyncTotalPages(data.pages || 1);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      fetchingRef.current = false;
    }
  }, [syncParams]);

  // Initial lookup data load
  useEffect(() => {
    if (compositesLoadedRef.current) return;
    fetchLatestComposites()
      .then((data) => {
        if (data) {
          setComposites(Object.keys(data));
          compositesLoadedRef.current = true;
        }
      })
      .catch(() => {});
  }, []);

  // Sync data based on active tab and filter parameters
  useEffect(() => {
    activeTab === "tasks" ? loadTasks() : loadSyncs();
  }, [activeTab, loadTasks, loadSyncs]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      activeTab === "tasks" ? loadTasks() : loadSyncs();
    }, 60000);
    return () => clearInterval(interval);
  }, [activeTab, loadTasks, loadSyncs]);

  return (
    <div className="dashboard">
      <div className="container">
        <header className="header-section">
          <h1>Twilight Dashboard</h1>
          <nav className="tabs">
            {(["tasks", "syncs"] as const).map((tab) => (
              <button
                key={tab}
                className={`tab-button ${activeTab === tab ? "active" : ""}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
            <Link className="tab-button" href="/">
              Back
            </Link>
          </nav>
        </header>

        {error && <div className="error-banner">{error}</div>}

        {activeTab === "tasks" ? (
          <div className="tab-content active">
            <div className="action-bar">
              <div className="filters">
                <FilterGroup
                  label="Composite"
                  value={taskParams.composite}
                  options={composites.map((c) => ({
                    label: formatComposite(c),
                    value: c
                  }))}
                  onChange={(v) =>
                    setTaskParams((p) => ({ ...p, composite: v, page: 1 }))
                  }
                />
                <FilterGroup
                  label="Priority"
                  value={taskParams.priority}
                  options={["low", "normal", "high"].map((v) => ({
                    label: v.toUpperCase(),
                    value: v
                  }))}
                  onChange={(v) =>
                    setTaskParams((p) => ({ ...p, priority: v, page: 1 }))
                  }
                />
                <FilterGroup
                  label="Status"
                  value={taskParams.status}
                  options={["pending", "processing", "completed", "failed"].map(
                    (v) => ({ label: v.toUpperCase(), value: v })
                  )}
                  onChange={(v) =>
                    setTaskParams((p) => ({ ...p, status: v, page: 1 }))
                  }
                />
              </div>
              <button className="add-button" onClick={() => setShowModal(true)}>
                + Add Task
              </button>
            </div>

            <DataList length={tasks.length} emptyText="No tasks found">
              {tasks.map((t) => (
                <TaskCard
                  key={t.task_id}
                  task={t}
                  onViewProfile={handleViewProfile}
                />
              ))}
            </DataList>

            <Pagination
              current={taskParams.page}
              total={taskTotalPages}
              onChange={(p) => setTaskParams((prev) => ({ ...prev, page: p }))}
            />
          </div>
        ) : (
          <div className="tab-content active">
            <div className="action-bar">
              <div className="filters">
                <FilterGroup
                  label="Status"
                  value={syncParams.status}
                  options={["pending", "running", "completed", "failed"].map(
                    (v) => ({ label: v.toUpperCase(), value: v })
                  )}
                  onChange={(v) =>
                    setSyncParams((p) => ({ ...p, status: v, page: 1 }))
                  }
                />
              </div>
            </div>

            <DataList length={syncs.length} emptyText="No sync data found">
              {syncs.map((s) => (
                <SyncCard key={s.timestamp} sync={s} />
              ))}
            </DataList>

            <Pagination
              current={syncParams.page}
              total={syncTotalPages}
              onChange={(p) => setSyncParams((prev) => ({ ...prev, page: p }))}
            />
          </div>
        )}
      </div>

      <AddTaskModal
        show={showModal}
        onClose={() => setShowModal(false)}
        composites={composites}
        onCreated={loadTasks}
      />

      <ProfileModal
        show={showProfile}
        onClose={() => setShowProfile(false)}
        taskId={selectedTaskId}
      />
    </div>
  );
}
