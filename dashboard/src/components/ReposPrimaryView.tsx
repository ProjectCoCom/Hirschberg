/**
 * Summary: React UI component 'Reposprimaryview'.
 *
 * What it does: Renders the 'Reposprimaryview' dashboard interface, manages localized state, and handles user actions.
 *
 * How it fits in: Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */



import { useCallback, useEffect, useState } from "react";
import { OctopusGlyph } from "./EmptyOctopus";
import type { OctopusAnimation, OctopusExpression } from "./EmptyOctopus";

type RepoCard = {
  name: string;
  fullName: string;
  defaultBranch: string;
  isPrivate: boolean;
  tasks: TaskItem[];
};

type TaskItem = {
  id: string;
  prompt: string;
  status: string;
  sessionId?: string;
  createdAt?: string;
};

const CARD_COLORS = ["#7c3aed", "#00e5ff", "#ff6b2b", "#00ffaa", "#ff2d6b", "#bf5fff"];
const CARD_ANIMATIONS: OctopusAnimation[] = ["sway", "walk", "bounce", "float", "jog", "idle"];
const CARD_EXPRESSIONS: OctopusExpression[] = ["normal", "happy", "surprised", "angry"];

const hashStr = (s: string): number => {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
};

export const ReposPrimaryView = () => {
  const [repos, setRepos] = useState<RepoCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasGithubKey, setHasGithubKey] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/api/settings/status").then((r) => {
      if (!r.ok) { setHasGithubKey(true); return null; }
      return r.json();
    }).then((d) => {
      if (!d) return;
      const ghClassic = d.github_token?.status === "active";
      const ghFg = d.github_fg_token?.status === "active";
      setHasGithubKey(ghClassic || ghFg);
    }).catch(() => setHasGithubKey(true));
  }, []);

  const fetchRepos = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/deck/tentacles");
      if (!res.ok) throw new Error("fetch failed");
      const data = await res.json();
      const tentacles = Array.isArray(data) ? data : data?.tentacles ?? [];
      const cards: RepoCard[] = tentacles.map((t: any) => ({
        name: t.name ?? t.tentacleId ?? "unknown",
        fullName: t.description ?? t.name ?? "",
        defaultBranch: "main",
        isPrivate: false,
        tasks: (t.todoItems ?? t.todos ?? []).map((todo: any, i: number) => ({
          id: `${t.tentacleId}-${i}`,
          prompt: todo.text ?? todo.label ?? "",
          status: todo.done ? "completed" : "pending",
        })),
      }));
      setRepos(cards);
    } catch {
      setRepos([]);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => { void fetchRepos(); }, [fetchRepos]);

  const completedCount = repos.reduce((s, r) => s + r.tasks.filter(t => t.status === "completed").length, 0);
  const totalTasks = repos.reduce((s, r) => s + r.tasks.length, 0);

  return (
    <section className="repos-view" aria-label="Repos primary view" style={{ position: "relative" }}>
      {!hasGithubKey && (
        <div className="apis-setup-overlay">
          <div className="apis-setup-card">
            <h3>GitHub API Key Required</h3>
            <p>Configure your GitHub token in Settings to view connected repos and tasks.</p>
            <button type="button" className="apis-setup-btn" onClick={() => { window.dispatchEvent(new CustomEvent("navigate", { detail: 8 })); }}>
              Go to Settings
            </button>
          </div>
        </div>
      )}
      <header className="repos-header">
        <h2>Repos</h2>
        <span className="repos-summary">
          {repos.length} repos · {completedCount}/{totalTasks} tasks done
        </span>
        <input
          type="text"
          className="repos-search"
          placeholder="Search repos or tasks..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button type="button" className="repos-refresh-btn" onClick={fetchRepos} disabled={isLoading}>
          {isLoading ? "Loading..." : "Refresh"}
        </button>
      </header>
      <div className="repos-grid">
        {repos.length === 0 && !isLoading && (
          <p className="repos-empty">No repos connected. Connect repos via Jules to see them here.</p>
        )}
        {repos.filter((r) => {
          if (!search) return true;
          const q = search.toLowerCase();
          return r.name.toLowerCase().includes(q) || r.fullName.toLowerCase().includes(q) || r.tasks.some(t => t.prompt.toLowerCase().includes(q));
        }).map((repo) => {
          const h = hashStr(repo.name);
          const color = CARD_COLORS[h % CARD_COLORS.length]!;
          const anim = CARD_ANIMATIONS[h % CARD_ANIMATIONS.length]!;
          const expr = CARD_EXPRESSIONS[h % CARD_EXPRESSIONS.length]!;
          const done = repo.tasks.filter(t => t.status === "completed").length;
          return (
            <div key={repo.name} className="repo-card">
              <header className="repo-card-header" style={{ borderTopColor: color }}>
                <div className="repo-card-octopus">
                  <OctopusGlyph color={color} animation={anim} expression={expr} scale={2} />
                </div>
                <div className="repo-card-title">
                  <h3>{repo.name}</h3>
                  {repo.fullName && <span className="repo-card-desc">{repo.fullName}</span>}
                </div>
                <span className="repo-card-status">{done}/{repo.tasks.length} done</span>
              </header>
              <ul className="repo-card-tasks">
                {repo.tasks.length === 0 && <li className="repo-card-empty">No tasks</li>}
                {repo.tasks.map((task) => (
                  <li key={task.id} className={`repo-card-task ${task.status === "completed" ? "is-done" : ""}`}>
                    <span className="repo-card-task-check">{task.status === "completed" ? "✓" : "○"}</span>
                    <span className="repo-card-task-text">{task.prompt}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
};
