/**
 * Custom React hook 'Uselivetaskstatus'.
 *
 * Responsibilities:
 * Abstracts state management, data polling, or backend API actions for 'Uselivetaskstatus' into a reusable hook.
 *
 * Coupling:
 * Consumed by React UI components inside the 'dashboard/src/components' component tree.
 */


import { useEffect, useRef, useState } from "react";

export type LiveTask = {
  id: string;
  status: string;
  repo_owner: string;
  repo_name: string;
  prompt: string;
  session_id: string | null;
  updated_at: string;
};

export function useLiveTaskStatus() {
  const [tasks, setTasks] = useState<LiveTask[]>([]);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastJsonRef = useRef("");

  useEffect(() => {
    const fetchTasks = () => {
      fetch("/api/terminals")
        .then((r) => r.json())
        .then((data) => {
          if (!Array.isArray(data)) return;
          const mapped = data.map((t: any) => ({
            id: t.terminalId ?? t.id ?? "",
            status: t.state === "live" ? "running" : (t.state === "queued" ? "pending" : "completed"),
            repo_owner: (t.tentacleId ?? "").split("/")[0] ?? "",
            repo_name: (t.tentacleId ?? "").split("/")[1] ?? "",
            prompt: t.label ?? t.tentacleName ?? "",
            session_id: t.sessionId ?? null,
            updated_at: t.createdAt ?? "",
          }));
          const json = JSON.stringify(mapped);
          if (json !== lastJsonRef.current) {
            lastJsonRef.current = json;
            setTasks(mapped);
          }
        })
        .catch(() => {});
    };

    fetchTasks();
    pollingRef.current = setInterval(fetchTasks, 10000);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  return tasks;
}
