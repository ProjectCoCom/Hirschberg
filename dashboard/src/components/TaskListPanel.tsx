/**
 * Summary: React UI component 'Tasklistpanel'.
 *
 * What it does: Renders the 'Tasklistpanel' dashboard interface, manages localized state, and handles user actions.
 *
 * How it fits in: Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */



import type { LiveTask } from "../app/hooks/useLiveTaskStatus";

type Props = {
  tasks: LiveTask[];
  visible: boolean;
};

const STATUS_COLORS: Record<string, string> = {
  running: "#00e5ff",
  completed: "#25d366",
  failed: "#ef4444",
  pending: "#6b7a90",
  queued: "#a78bfa",
  blocked: "#f59e0b",
};

export const TaskListPanel = ({ tasks, visible }: Props) => {
  if (!visible || tasks.length === 0) return null;

  return (
    <aside className="task-list-panel">
      <h3 className="task-list-title">Tasks</h3>
      <div className="task-list-items">
        {tasks.map((t) => (
          <div key={t.id} className="task-list-item">
            <span
              className="task-list-dot"
              style={{ background: STATUS_COLORS[t.status] ?? "#6b7a90" }}
            />
            <div className="task-list-info">
              <span className="task-list-desc">{t.prompt?.slice(0, 60) || "No description"}</span>
              <span className="task-list-meta">
                {t.repo_owner}/{t.repo_name} - {t.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
};
