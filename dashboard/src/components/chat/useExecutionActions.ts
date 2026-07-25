/**
 * React UI component 'Useexecutionactions'.
 *
 * Responsibilities:
 * Renders the 'Useexecutionactions' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { useCallback, useState } from "react";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  model?: string;
};

type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  providerId?: string;
  model?: string;
};

type ExecutionState = {
  planReady: boolean;
  isExecuting: boolean;
  executionStatus: string | null;
};

type ExecutionActions = ExecutionState & {
  setPlanReady: (v: boolean) => void;
  handleApprove: () => void;
  handleAutoMode: () => void;
  resetExecution: () => void;
};

export function useExecutionActions(
  activeConv: Conversation | null,
  activeConvId: string | null,
  selectedRepo: string,
  selectedProviderType: string,
  selectedModel: string,
  setConversations: React.Dispatch<React.SetStateAction<Conversation[]>>,
  setMode: (m: "ask" | "plan" | "build" | "auto") => void,
): ExecutionActions {
  const [planReady, setPlanReady] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionStatus, setExecutionStatus] = useState<string | null>(null);

  const handleApprove = useCallback(() => {
    if (!activeConv || !selectedRepo || isExecuting) return;
    const lastAssistant = [...activeConv.messages].reverse().find((m) => m.role === "assistant");
    if (!lastAssistant) return;

    const jsonMatch = lastAssistant.content.match(/```json\s*([\s\S]*?)```/);
    const planJson = jsonMatch ? jsonMatch[1].trim() : lastAssistant.content;

    setIsExecuting(true);
    setExecutionStatus("Dispatching tasks to Jules...");
    setPlanReady(false);

    fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan_json: planJson,
        repo_owner: "iceyxsm",
        repo_name: selectedRepo,
        provider_type: selectedProviderType,
        model: selectedModel,
      }),
    })
      .then(async (r) => {
        if (!r.ok) {
          let detail = `Execute failed (${r.status})`;
          try {
            const d = await r.json();
            if (d.detail) detail = d.detail;
          } catch {}
          throw new Error(detail);
        }
        return r.json();
      })
      .then((data) => {
        const status = data.status === "completed" ? "All tasks completed" : `Execution: ${data.status}`;
        setExecutionStatus(status);
        const lines = (data.results ?? []).map((r: any) =>
          `- ${r.task_id}: ${r.status}${r.pr_url ? ` (${r.pr_url})` : ""}${r.error ? ` [${r.error}]` : ""}`
        );
        const summaryMsg: Message = {
          id: `m-${Date.now()}`,
          role: "assistant",
          content: `Execution ${data.status}.\n\n${lines.join("\n")}`,
          timestamp: new Date().toISOString(),
          model: "orchestrator",
        };
        setConversations((prev) => prev.map((c) => c.id === activeConvId ? { ...c, messages: [...c.messages, summaryMsg] } : c));
      })
      .catch((e) => setExecutionStatus(`Failed: ${e.message}`))
      .finally(() => setIsExecuting(false));
  }, [activeConv, selectedRepo, activeConvId, setConversations, isExecuting, selectedProviderType, selectedModel]);

  const handleAutoMode = useCallback(() => {
    if (!selectedRepo || !selectedProviderType || !selectedModel) return;
    const goal = window.prompt("Describe the end goal for auto mode:");
    if (!goal) return;

    setMode("auto");
    setIsExecuting(true);
    setExecutionStatus("Auto mode running...");

    fetch("/api/execute/auto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_owner: "iceyxsm",
        repo_name: selectedRepo,
        goal,
        provider_type: selectedProviderType,
        model: selectedModel,
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        setExecutionStatus(`Auto: ${data.status} (${data.sessions_used} sessions)`);
        const msg: Message = {
          id: `m-${Date.now()}`,
          role: "assistant",
          content: `Auto mode ${data.status}. Sessions used: ${data.sessions_used}.\n${(data.errors ?? []).join("\n")}`,
          timestamp: new Date().toISOString(),
          model: "orchestrator",
        };
        setConversations((prev) => prev.map((c) => c.id === activeConvId ? { ...c, messages: [...c.messages, msg] } : c));
      })
      .catch((e) => setExecutionStatus(`Auto failed: ${e.message}`))
      .finally(() => setIsExecuting(false));
  }, [selectedRepo, selectedProviderType, selectedModel, activeConvId, setConversations, setMode]);

  const resetExecution = useCallback(() => {
    setPlanReady(false);
    setExecutionStatus(null);
  }, []);

  return { planReady, isExecuting, executionStatus, setPlanReady, handleApprove, handleAutoMode, resetExecution };
}
