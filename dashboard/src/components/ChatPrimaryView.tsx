/**
 * React UI component 'Chatprimaryview'.
 *
 * Responsibilities:
 * Renders the 'Chatprimaryview' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { memo, useCallback, useEffect, useRef, useState } from "react";
import { marked } from "marked";
import { TaskListPanel } from "./TaskListPanel";
import { useLiveTaskStatus } from "../app/hooks/useLiveTaskStatus";
import { SearchableDropdown } from "./chat/SearchableDropdown";
import { useExecutionActions } from "./chat/useExecutionActions";

marked.setOptions({ breaks: true, gfm: true });

function wrapSectionsCollapsible(html: string): string {
  const lines = html.split("\n");
  const result: string[] = [];
  let inSection = false;

  for (const line of lines) {
    const headerMatch = line.match(/^<h([23])[^>]*>(.*?)<\/h[23]>/);
    if (headerMatch) {
      if (inSection) result.push("</details>");
      result.push(`<details><summary>${headerMatch[2]}</summary>`);
      inSection = true;
    } else {
      result.push(line);
    }
  }
  if (inSection) result.push("</details>");
  return result.join("\n");
}

const ChatMessageBubble = memo(({ msg, renderPlanJson, parseMessageActions, handleAction }: {
  msg: { id: string; role: string; content: string; model?: string };
  renderPlanJson: (text: string) => string | null;
  parseMessageActions: (content: string) => { text: string; action: { type: string; payload: string } | null };
  handleAction: (type: string, payload: string) => void;
}) => {
  const { text, action } = msg.role === "assistant" ? parseMessageActions(msg.content) : { text: msg.content, action: null };
  const rendered = msg.role === "assistant"
    ? (renderPlanJson(text) || wrapSectionsCollapsible(marked.parse(text) as string))
    : text;
  return (
    <div className={`chat-msg chat-msg--${msg.role}`}>
      <span className="chat-msg-role">{msg.role === "user" ? "You" : msg.model ?? "AI"}</span>
      {msg.role === "assistant"
        ? <div className="chat-msg-content chat-md" dangerouslySetInnerHTML={{ __html: rendered }} />
        : <div className="chat-msg-content">{text}</div>
      }
      {action && (
        <button type="button" className="chat-action-btn" onClick={() => handleAction(action.type, action.payload)}>
          {action.type === "SWITCH_MODE" && `Switch to ${action.payload.toUpperCase()} mode`}
          {action.type === "APPROVE_PLAN" && "Approve Plan"}
          {action.type === "APPROVE_BUILD" && "Approve Build"}
        </button>
      )}
    </div>
  );
});

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
  updatedAt: string;
  providerId?: string;
  model?: string;
  repo?: string;
  providerType?: string;
};

type ProviderGroup = { type: string; keyCount: number; ids: string[] };

class ModelUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ModelUnavailableError";
  }
}

class RateLimitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RateLimitError";
  }
}

function hasPlanJson(text: string): boolean {
  const match = text.match(/```json\s*([\s\S]*?)```/);
  if (!match) return false;
  try {
    const parsed = JSON.parse(match[1]);
    return Array.isArray(parsed.tasks) && parsed.tasks.length > 0;
  } catch {
    return false;
  }
}

export const ChatPrimaryView = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeConvIdRef = useRef<string | null>(null);

  const [providerTypes, setProviderTypes] = useState<ProviderGroup[]>([]);
  const [providersLoaded, setProvidersLoaded] = useState(false);
  const [selectedProviderType, setSelectedProviderType] = useState("");
  const [models, setModels] = useState<{ id: string; name: string }[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [modelsLoading, setModelsLoading] = useState(false);
  const [repos, setRepos] = useState<string[]>([]);
  const [selectedRepo, setSelectedRepo] = useState("");
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"ask" | "plan" | "build" | "auto">("ask");
  const [isStarted, setIsStarted] = useState(false);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [analyzingConvIds, setAnalyzingConvIds] = useState<Set<string>>(new Set());
  const [usage, setUsage] = useState({ tokensUsed: 0, tokensLimit: 0, rpmLimit: 40, requestsToday: 0 });
  const [chatSearch, setChatSearch] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteInput, setDeleteInput] = useState("");
  const [unreadConvIds, setUnreadConvIds] = useState<Set<string>>(new Set());
  const [showSummarizerSettings, setShowSummarizerSettings] = useState(false);
  const [showRateLimitPopup, setShowRateLimitPopup] = useState(false);
  const [summarizerMode, setSummarizerMode] = useState<"free" | "ai">("free");
  const [summarizerProvider, setSummarizerProvider] = useState("");
  const [summarizerModel, setSummarizerModel] = useState("");
  const [summarizerModels, setSummarizerModels] = useState<{ id: string; name: string; context_length?: number }[]>([]);
  const [summarizerLimit, setSummarizerLimit] = useState(10);
  const [showPromptsPopup, setShowPromptsPopup] = useState(false);
  const [promptsList, setPromptsList] = useState<{ id: string; name: string; content: string }[]>([]);
  const [promptsMode, setPromptsMode] = useState<"send" | "assign" | "master">("send");
  const [masterPromptId, setMasterPromptId] = useState<Set<string>>(new Set());
  const [assignedPromptId, setAssignedPromptId] = useState<Set<string>>(new Set());
  const [selectedPromptIds, setSelectedPromptIds] = useState<Set<string>>(new Set());
  const [promptsSearch, setPromptsSearch] = useState("");
  const [promptsHighlight, setPromptsHighlight] = useState(0);

  const tasks = useLiveTaskStatus();
  const activeConv = conversations.find((c) => c.id === activeConvId) ?? null;

  const exec = useExecutionActions(
    activeConv, activeConvId, selectedRepo,
    selectedProviderType, selectedModel, setConversations, setMode,
  );

  const fetchConversations = useCallback(() => {
    fetch("/api/conversations").then((r) => r.json()).then((d) => {
      const convs = (d.conversations ?? []).map((c: any) => ({
        id: c.id, title: c.title || "Untitled", messages: [], createdAt: c.created_at, updatedAt: c.updated_at || c.created_at, model: c.model, providerType: c.provider_type || "", repo: c.repo_name || "",
      }));
      convs.sort((a: Conversation, b: Conversation) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
      setConversations((prev) => {
        // Preserve already-loaded messages
        const msgMap = new Map(prev.map((c) => [c.id, c.messages]));
        return convs.map((c: Conversation) => ({ ...c, messages: msgMap.get(c.id) ?? c.messages }));
      });
      setActiveConvId((prev) => prev ?? (convs.length > 0 ? convs[0].id : null));
    }).catch(() => {});
  }, []);

  useEffect(() => { fetchConversations(); }, [fetchConversations]);

  useEffect(() => { activeConvIdRef.current = activeConvId; }, [activeConvId]);  useEffect(() => {
    if (!activeConvId) return;
    setMessagesLoading(true);
    fetch(`/api/conversations/${activeConvId}/messages`)
      .then((r) => r.json())
      .then((d) => {
        const msgs: Message[] = (d.messages ?? []).map((m: any) => ({
          id: m.id ?? `m-${Date.now()}-${Math.random()}`,
          role: m.role,
          content: m.content,
          timestamp: m.created_at ?? m.timestamp ?? new Date().toISOString(),
          model: m.model,
        }));
        setConversations((prev) => prev.map((c) => c.id === activeConvId
          ? { ...c, messages: msgs.length > 0 ? msgs : c.messages }
          : c));
        setIsStarted(msgs.length > 0);
        if (msgs.length > 0) {
          if (msgs.some((m: Message) => m.role === "assistant" && hasPlanJson(m.content))) {
            exec.setPlanReady(true);
          }
        }
      })
      .catch(() => {})
      .finally(() => setMessagesLoading(false));
    setUnreadConvIds((prev) => {
      if (!prev.has(activeConvId)) return prev;
      const next = new Set(prev);
      next.delete(activeConvId);
      return next;
    });
    exec.resetExecution();
  }, [activeConvId]);

  // Restore provider/model/repo when conversation data becomes available
  const restoredConvRef = useRef<string | null>(null);
  useEffect(() => {
    if (!activeConvId || restoredConvRef.current === activeConvId) return;
    const conv = conversations.find((c) => c.id === activeConvId);
    if (!conv || !conv.model) return;
    restoredConvRef.current = activeConvId;
    setSelectedModel(conv.model);
    if (conv.repo) setSelectedRepo(conv.repo);
    if (conv.providerType) {
      setSelectedProviderType(conv.providerType);
    } else {
      const m = conv.model.toLowerCase();
      if (m.includes("deepseek")) setSelectedProviderType("deepseek");
      else if (m.includes("yi-") || m.includes("01-ai")) setSelectedProviderType("nvidia_nim");
      else if (m.includes("longcat")) setSelectedProviderType("longcat");
    }
  }, [activeConvId, conversations]);

  // Persist dropdown selections to the active conversation
  useEffect(() => {
    if (!activeConvId || !selectedModel) return;
    setConversations(prev => prev.map(c => c.id === activeConvId ? { ...c, model: selectedModel } : c));
  }, [selectedModel, activeConvId]);
  useEffect(() => {
    if (!activeConvId) return;
    setConversations(prev => prev.map(c => c.id === activeConvId ? { ...c, repo: selectedRepo } : c));
  }, [selectedRepo, activeConvId]);
  useEffect(() => {
    if (!activeConvId || !selectedProviderType) return;
    setConversations(prev => prev.map(c => c.id === activeConvId ? { ...c, providerType: selectedProviderType } : c));
  }, [selectedProviderType, activeConvId]);

  useEffect(() => {
    fetch("/api/providers").then((r) => r.json()).then((d) => {
      const enabled = (d.providers ?? []).filter((p: any) => p.enabled);
      const grouped: Record<string, ProviderGroup> = {};
      for (const p of enabled) {
        if (!grouped[p.provider_type]) grouped[p.provider_type] = { type: p.provider_type, keyCount: 0, ids: [] };
        grouped[p.provider_type].keyCount++;
        grouped[p.provider_type].ids.push(p.id);
      }
      const types = Object.values(grouped);
      setProviderTypes(types);
      if (types.length > 0) setSelectedProviderType((prev) => prev || types[0].type);
    }).catch(() => {}).finally(() => setProvidersLoaded(true));
  }, []);

  useEffect(() => {
    if (!selectedProviderType) return;
    const group = providerTypes.find((g) => g.type === selectedProviderType);
    if (!group || group.ids.length === 0) return;
    setModelsLoading(true);
    setModels([]);
    fetch(`/api/providers/${group.ids[0]}/models`).then((r) => r.json()).then((d) => {
      const raw = d.models ?? [];
      const seen = new Set<string>();
      const modelList = raw.filter((m: { id: string }) => {
        if (seen.has(m.id)) return false;
        seen.add(m.id);
        return true;
      });
      setModels(modelList);
      if (modelList.length > 0) {
        setSelectedModel((prev) => {
          if (prev && modelList.some((m: { id: string }) => m.id === prev)) return prev;
          return modelList[0].id;
        });
      }
      const lim = d.limits ?? {};
      setUsage((u) => ({ ...u, rpmLimit: (lim.rpm ?? 40) * group.keyCount, tokensLimit: (lim.rpd ?? 0) * group.keyCount }));
    }).catch(() => {}).finally(() => setModelsLoading(false));
  }, [selectedProviderType, providerTypes]);

  useEffect(() => {
    fetch("/api/github/repos").then((r) => r.json()).then((d) => {
      const names = [...new Set((d.repos ?? []).map((r: { name: string }) => r.name))] as string[];
      setRepos(names);
      if (names.length > 0) setSelectedRepo((prev) => prev && names.includes(prev) ? prev : names[0]);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    fetch("/api/settings/summarizer").then((r) => r.json()).then((d) => {
      if (d.mode) setSummarizerMode(d.mode);
      if (d.provider) setSummarizerProvider(d.provider);
      if (d.model) setSummarizerModel(d.model);
      if (d.limit) setSummarizerLimit(d.limit);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConv?.messages.length]);

  const handleSend = useCallback(() => {
    if (!input.trim() || !activeConvId) return;
    const sendingConvId = activeConvId;
    const userMsg: Message = { id: `m-${Date.now()}`, role: "user", content: input.trim(), timestamp: new Date().toISOString() };
    setConversations((prev) => prev.map((c) => c.id === sendingConvId ? { ...c, messages: [...c.messages, userMsg] } : c));
    const currentInput = input.trim();
    setInput("");
    setIsTyping(true);
    setUsage((u) => ({ ...u, requestsToday: u.requestsToday + 1, tokensUsed: u.tokensUsed + currentInput.length }));

    fetch(`/api/conversations/${sendingConvId}/messages`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "user", content: currentInput }),
    }).catch(() => {});

    const conv = conversations.find((c) => c.id === sendingConvId);
    const history = [...(conv?.messages ?? []), { role: "user", content: currentInput }]
      .map((m) => ({ role: m.role, content: m.content }));

    fetch("/api/chat/send", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider_type: selectedProviderType, model: selectedModel, messages: history,
        image_base64: imagePreview ?? undefined,
        repo: selectedRepo ? `iceyxsm/${selectedRepo}` : undefined, mode,
        conversation_id: activeConvId ?? undefined,
        system: masterPromptId.size > 0 ? promptsList.filter(p => masterPromptId.has(p.name)).map(p => p.content ?? "").join("\n\n") : undefined,
      }),
    })
      .then((r) => {
        if (r.status === 404) {
          return r.json().then((d: any) => { throw new ModelUnavailableError(d.detail ?? "Model not available"); });
        }
        if (r.status === 429) {
          return r.json().then((d: any) => { throw new RateLimitError(d.detail ?? "Rate limit exceeded"); });
        }
        return r.json();
      })
      .then((data) => {
        const content = data.response ?? data.detail ?? "No response";
        const assistantMsg: Message = { id: `m-${Date.now() + 1}`, role: "assistant", content, timestamp: new Date().toISOString(), model: selectedModel };
        const now = new Date().toISOString();
        setConversations((prev) => {
          const updated = prev.map((c) => c.id === sendingConvId ? { ...c, messages: [...c.messages, assistantMsg], updatedAt: now } : c);
          updated.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
          return updated;
        });
        setUnreadConvIds((prev) => {
          if (activeConvIdRef.current === sendingConvId) return prev;
          const next = new Set(prev);
          next.add(sendingConvId);
          return next;
        });
        setUsage((u) => ({ ...u, tokensUsed: u.tokensUsed + content.length }));
        if (hasPlanJson(content)) {
          exec.setPlanReady(true);
        } else if (mode === "plan") {
          setConversations((prev) => {
            const conv = prev.find((c) => c.id === sendingConvId);
            if (conv?.messages.some((m) => m.role === "assistant" && hasPlanJson(m.content))) {
              exec.setPlanReady(true);
            }
            return prev;
          });
        }
        fetch(`/api/conversations/${sendingConvId}/messages`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role: "assistant", content }),
        }).catch(() => {});
      })
      .catch((e) => {
        const isModelError = e instanceof ModelUnavailableError;
        const isRateLimit = e instanceof RateLimitError;
        if (isRateLimit) {
          setShowRateLimitPopup(true);
          return;
        }
        const content = isModelError
          ? `${e.message}\n\nPlease select a different model from the dropdown above.`
          : "Failed to get response. Check backend.";
        const errMsg: Message = { id: `m-${Date.now() + 1}`, role: "assistant", content, timestamp: new Date().toISOString() };
        setConversations((prev) => prev.map((c) => c.id === sendingConvId ? { ...c, messages: [...c.messages, errMsg] } : c));
      })
      .finally(() => { setIsTyping(false); setImagePreview(null); });
  }, [input, activeConvId, selectedModel, selectedProviderType, conversations, imagePreview, mode, exec, masterPromptId, promptsList]);

  const handleStart = useCallback(() => {
    if (!selectedRepo || !selectedProviderType || !selectedModel || !activeConvId) return;
    const startingConvId = activeConvId;
    setAnalyzingConvIds((prev) => new Set(prev).add(startingConvId));
    fetch(`/api/repos/iceyxsm/${selectedRepo}/analyze`, { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        if (!data.xml) throw new Error(data.detail ?? "Analysis failed");
        return fetch("/api/chat/send", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider_type: selectedProviderType, model: selectedModel,
            messages: [{ role: "user", content: "Analyze this repo and give me a structured summary: project name, tech stack, structure, and what it does." }],
            system: `You are a code analyst. Respond directly without preamble like "Based on the provided..." or "Here is a summary...". Start with the actual content.\n\nAnalyze this codebase and provide a structured summary:\n\n${data.xml.slice(0, 80000)}`,
            repo: `iceyxsm/${selectedRepo}`,
          }),
        });
      })
      .then((r) => {
        if (!r) return null;
        if (r.status === 404) {
          return r.json().then((d: any) => { throw new ModelUnavailableError(d.detail ?? "Model not available"); });
        }
        return r.json();
      })
      .then((data) => {
        if (data?.response) {
          const msg: Message = { id: `m-${Date.now()}`, role: "assistant", content: data.response, timestamp: new Date().toISOString(), model: selectedModel };
          const now = new Date().toISOString();
          setConversations((prev) => {
            const updated = prev.map((c) => c.id === startingConvId
              ? { ...c, messages: [...c.messages, msg], model: selectedModel, title: selectedRepo, updatedAt: now }
              : c);
            updated.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
            return updated;
          });
          setIsStarted(true);
          setUnreadConvIds((prev) => {
            if (activeConvIdRef.current === startingConvId) return prev;
            return new Set(prev).add(startingConvId);
          });
          fetch(`/api/conversations/${startingConvId}`, {
            method: "PATCH", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: selectedRepo, model: selectedModel }),
          }).catch(() => {});
          fetch(`/api/conversations/${startingConvId}/messages`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role: "assistant", content: data.response }),
          }).catch(() => {});
        }
      })
      .catch((e) => {
        const isModelError = e instanceof ModelUnavailableError;
        const content = isModelError
          ? `${e.message}\n\nPlease select a different model from the dropdown above and click Start again.`
          : `Start failed: ${e.message}`;
        const errMsg: Message = { id: `m-${Date.now()}`, role: "assistant", content, timestamp: new Date().toISOString() };
        setConversations((prev) => prev.map((c) => c.id === startingConvId ? { ...c, messages: [...c.messages, errMsg] } : c));
      })
      .finally(() => {
        setAnalyzingConvIds((prev) => { const next = new Set(prev); next.delete(startingConvId); return next; });
      });
  }, [selectedRepo, selectedProviderType, selectedModel, activeConvId]);

  const handleNewConversation = useCallback(() => {
    const body = { title: "New conversation", mode, repo_owner: "iceyxsm", repo_name: selectedRepo, provider_type: selectedProviderType, model: selectedModel };
    fetch("/api/conversations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then((r) => r.json())
      .then((data) => {
        const newConv: Conversation = { id: data.id, title: body.title, messages: [], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), model: selectedModel };
        setConversations((prev) => [newConv, ...prev]);
        setActiveConvId(data.id);
      })
      .catch(() => {
        const newConv: Conversation = { id: `conv-${Date.now()}`, title: "New conversation", messages: [], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), model: selectedModel };
        setConversations((prev) => [newConv, ...prev]);
        setActiveConvId(newConv.id);
      });
    setIsStarted(false);
    exec.resetExecution();
  }, [exec, selectedModel, selectedProviderType, selectedRepo, mode]);

  const handleImageChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);
    e.target.value = "";
  }, []);

  const providerItems = providerTypes.map((g) => ({
    id: g.type,
    label: `${g.type.replace("_", " ").toUpperCase()} (${g.keyCount} key${g.keyCount > 1 ? "s" : ""})`,
  }));
  const modelItems = models.map((m) => ({ id: m.id, label: m.name }));
  const repoItems = repos.map((r) => ({ id: r, label: r }));
  const parseMessageActions = (content: string) => {
    const actionMatch = content.match(/\[ACTION:(\w+)(?::([^\]]*))?\]/);
    if (!actionMatch) return { text: content, action: null };
    const text = content.replace(/\[ACTION:\w+(?::[^\]]*)?\]/, "").trim();
    return { text, action: { type: actionMatch[1], payload: actionMatch[2] ?? "" } };
  };

  const handleAction = (actionType: string, payload: string) => {
    if (actionType === "SWITCH_MODE") {
      const newMode = payload.toLowerCase() as "ask" | "plan" | "build" | "auto";
      if (["ask", "plan", "build", "auto"].includes(newMode)) setMode(newMode);
    } else if (actionType === "APPROVE_PLAN") {
      exec.handleApprove();
    }
  };

  const renderPlanJson = (text: string): string | null => {
    const jsonMatch = text.match(/```json\s*([\s\S]*?)```/);
    if (!jsonMatch) return null;
    try {
      const plan = JSON.parse(jsonMatch[1]);
      if (!plan.tasks) return null;
      const before = text.slice(0, text.indexOf("```json")).trim();
      let after = text.slice(text.indexOf("```", text.indexOf("```json") + 7) + 3).trim();
      after = after.replace(/\[ACTION:\w+(?::[^\]]*)?\]/g, "").replace(/\{[\s\S]*"tasks"[\s\S]*\}$/m, "").trim();
      let html = before ? marked.parse(before) as string : "";
      html += `<div class="chat-plan-tasks">`;
      for (const task of plan.tasks) {
        html += `<div class="chat-plan-task">`;
        html += `<div class="chat-plan-task-header"><span class="chat-plan-task-id">${task.id}</span><span class="chat-plan-task-branch">${task.branch || ""}</span></div>`;
        html += `<div class="chat-plan-task-desc">${task.description}</div>`;
        if (task.exit_criteria) html += `<div class="chat-plan-task-criteria">${task.exit_criteria}</div>`;
        if (task.dependencies?.length) html += `<div class="chat-plan-task-deps">Depends: ${task.dependencies.join(", ")}</div>`;
        html += `</div>`;
      }
      html += `</div>`;
      if (after) html += marked.parse(after) as string;
      return html;
    } catch { return null; }
  };

  const showTasks = (mode === "plan" || mode === "build" || mode === "auto") && tasks.length > 0;
  const isAnalyzing = activeConvId ? analyzingConvIds.has(activeConvId) : false;
  const hasExistingMessages = (activeConv?.messages.length ?? 0) > 0;
  const chatEnabled = isStarted || hasExistingMessages;

  return (
    <section className="chat-view" aria-label="Chat primary view" style={{ position: "relative" }}>
      {providersLoaded && providerTypes.length === 0 && (
        <div className="apis-setup-overlay">
          <div className="apis-setup-card">
            <h3>AI Provider Key Required</h3>
            <p>Add at least one AI provider API key to start chatting. Free options include Groq, Google AI Studio, and NVIDIA NIM.</p>
            <button type="button" className="apis-setup-btn" onClick={() => { window.dispatchEvent(new CustomEvent("navigate", { detail: 6 })); }}>
              Go to APIs
            </button>
          </div>
        </div>
      )}
      <aside className="chat-sidebar">
        <div className="chat-sidebar-toolbar">
          <button type="button" className="chat-new-btn" onClick={handleNewConversation}>+ New Chat</button>
          <button type="button" className="chat-refresh-btn" onClick={fetchConversations} aria-label="Refresh chats">R</button>
        </div>
        <input className="chat-search" type="text" placeholder="Search chats..." value={chatSearch} onChange={(e) => setChatSearch(e.target.value)} />
        <div className="chat-conv-list">
          {conversations.filter((c) => c.title.toLowerCase().includes(chatSearch.toLowerCase())).map((c) => (
            <button key={c.id} type="button" className={`chat-conv-item${activeConvId === c.id ? " is-active" : ""}${unreadConvIds.has(c.id) && activeConvId !== c.id ? " has-unread" : ""}`} onClick={() => { setActiveConvId(c.id); setUnreadConvIds((prev) => { const next = new Set(prev); next.delete(c.id); return next; }); }}>
              <div className="chat-conv-row">
                <span className="chat-conv-title">{c.title}</span>
                <span className="chat-conv-id">{c.id.slice(-6)}</span>
              </div>
              <div className="chat-conv-row">
                <span className="chat-conv-meta">{c.model ? c.model.split("/").pop() : "no model"}</span>
                <span className="chat-conv-date">{new Date(c.createdAt).toLocaleDateString()} {new Date(c.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
              </div>
            </button>
          ))}
        </div>
      </aside>
      <main className="chat-main">
        <header className="chat-header">
          <span className="chat-header-label">Model:</span>
          <SearchableDropdown items={providerItems} selected={selectedProviderType} onSelect={setSelectedProviderType} placeholder="No providers" searchPlaceholder="Search providers..." />
          <SearchableDropdown items={modelItems} selected={selectedModel} onSelect={setSelectedModel} placeholder="Select model" searchPlaceholder="Search models..." disabled={modelsLoading} />
          <div className="chat-header-spacer" />
          <span className="chat-header-label">Repo:</span>
          <SearchableDropdown items={repoItems} selected={selectedRepo} onSelect={setSelectedRepo} placeholder="Select repo" searchPlaceholder="Search repos..." disabled={!!activeConv && activeConv.messages.length > 0} />
          <div className="chat-header-spacer" />
          <div className="chat-mode-selector">
            {(["ask", "plan", "build"] as const).map((m) => (
              <button key={m} type="button" className={`chat-mode-btn${mode === m ? " is-active" : ""}`} onClick={() => setMode(m)}>{m.toUpperCase()}</button>
            ))}
            <button type="button" className={`chat-mode-btn${mode === "auto" ? " is-active" : ""}`} onClick={exec.handleAutoMode} disabled={!selectedRepo || !selectedModel || exec.isExecuting}>AUTO</button>
          </div>
          {exec.planReady && !exec.isExecuting && (
            <button type="button" className="chat-approve-btn" onClick={exec.handleApprove}>Approve Plan</button>
          )}
          {exec.executionStatus && <span className="chat-exec-status">{exec.executionStatus}</span>}
          {!isStarted && !messagesLoading && activeConv && (
            <button type="button" className="chat-start-btn" onClick={handleStart} disabled={!selectedRepo || !selectedModel || isAnalyzing}>
              {isAnalyzing ? "Analyzing..." : "Start"}
            </button>
          )}
          <div className="chat-usage-stats">
            <div className="chat-usage-bar-group">
              <span className="chat-usage-label">Tokens</span>
              <div className="chat-usage-bar"><div className="chat-usage-bar-fill" style={{ width: `${usage.tokensLimit > 0 ? Math.max(0, 100 - (usage.tokensUsed / usage.tokensLimit) * 100) : 100}%` }} /></div>
              <span className="chat-usage-value">{usage.tokensUsed.toLocaleString()}{usage.tokensLimit > 0 ? `/${usage.tokensLimit.toLocaleString()}` : ""}</span>
            </div>
            <div className="chat-usage-bar-group">
              <span className="chat-usage-label">RPM</span>
              <div className="chat-usage-bar"><div className="chat-usage-bar-fill" style={{ width: `${Math.max(0, 100 - (usage.requestsToday / usage.rpmLimit) * 100)}%` }} /></div>
              <span className="chat-usage-value">{usage.requestsToday}/{usage.rpmLimit}</span>
            </div>
          </div>
          {activeConv && <button type="button" className="chat-delete-btn" onClick={() => setShowDeleteConfirm(true)}>Delete</button>}
          {showDeleteConfirm && (
            <div className="chat-delete-popup">
              <div className="chat-delete-popup-inner">
                <p>Type <strong>delete chat</strong> to confirm deletion</p>
                <input type="text" value={deleteInput} onChange={(e) => setDeleteInput(e.target.value)} placeholder="delete chat" autoFocus onKeyDown={(e) => {
                  if (e.key === "Enter" && deleteInput === "delete chat" && activeConvId) {
                    fetch(`/api/conversations/${activeConvId}`, { method: "DELETE" }).catch(() => {});
                    setConversations((prev) => prev.filter((c) => c.id !== activeConvId));
                    const remaining = conversations.filter((c) => c.id !== activeConvId);
                    setActiveConvId(remaining.length > 0 ? remaining[0].id : null);
                    setShowDeleteConfirm(false);
                    setDeleteInput("");
                    setIsStarted(false);
                  }
                }} />
                <div className="chat-delete-popup-actions">
                  <button type="button" onClick={() => { setShowDeleteConfirm(false); setDeleteInput(""); }}>Cancel</button>
                  <button type="button" className="chat-delete-confirm-btn" disabled={deleteInput !== "delete chat"} onClick={() => {
                    if (!activeConvId) return;
                    fetch(`/api/conversations/${activeConvId}`, { method: "DELETE" }).catch(() => {});
                    setConversations((prev) => prev.filter((c) => c.id !== activeConvId));
                    const remaining = conversations.filter((c) => c.id !== activeConvId);
                    setActiveConvId(remaining.length > 0 ? remaining[0].id : null);
                    setShowDeleteConfirm(false);
                    setDeleteInput("");
                    setIsStarted(false);
                  }}>Delete</button>
                </div>
              </div>
            </div>
          )}
        </header>
        {activeConv ? (
          <>
            <div className="chat-body-row">
              <div className="chat-messages">
                {isAnalyzing && (
                  <div className="chat-setup-overlay">
                    <div className="chat-setup-spinner" />
                    <span className="chat-setup-text">Setting up — analyzing repository...</span>
                  </div>
                )}
                {!isStarted && !isAnalyzing && !messagesLoading && activeConv.messages.length === 0 && (
                  <div className="chat-setup-overlay">
                    <span className="chat-setup-text">Select a repo and click Start to begin</span>
                  </div>
                )}
                {activeConv.messages.map((msg) => (
                  <ChatMessageBubble key={msg.id} msg={msg} renderPlanJson={renderPlanJson} parseMessageActions={parseMessageActions} handleAction={handleAction} />
                ))}
                {isTyping && (
                  <div className="chat-msg chat-msg--assistant">
                    <span className="chat-msg-role">AI</span>
                    <div className="chat-msg-content chat-msg-typing">Thinking...</div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
              <TaskListPanel tasks={tasks} visible={showTasks} />
            </div>
            <div className={`chat-input-bar${!chatEnabled ? " chat-input-bar--disabled" : ""}`}>
              <button type="button" className="chat-settings-btn" onClick={() => setShowSummarizerSettings(true)} title="Summarizer settings">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </button>
              <input ref={imageInputRef} type="file" accept="image/*" className="chat-image-input-hidden" onChange={handleImageChange} />
              <button type="button" className="chat-image-btn" onClick={() => imageInputRef.current?.click()} title="Attach image">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
              </button>
              {imagePreview && (
                <div className="chat-image-preview">
                  <img src={imagePreview} alt="Attached" />
                  <button type="button" className="chat-image-remove" onClick={() => setImagePreview(null)}>x</button>
                </div>
              )}
              <input className="chat-input" type="text" placeholder={chatEnabled ? "Type a message..." : "Click Start to begin"} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }} disabled={!chatEnabled} />
              <button type="button" className="chat-prompts-btn" onClick={() => { setShowPromptsPopup(true); fetch("/api/prompts").then(r => r.json()).then(d => setPromptsList(Array.isArray(d?.prompts) ? d.prompts : [])).catch(() => {}); }} title="Prompts / Skills">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                </svg>
              </button>
              <button type="button" className="chat-send-btn" onClick={handleSend} disabled={!input.trim() || isTyping || !chatEnabled}>Send</button>
            </div>
            {showSummarizerSettings && (
              <div className="chat-summarizer-popup">
                <div className="chat-summarizer-popup-inner">
                  <div className="chat-summarizer-header">
                    <h4>Context Summarizer</h4>
                    <button type="button" className="chat-summarizer-close" onClick={() => setShowSummarizerSettings(false)}>x</button>
                  </div>
                  <div className="chat-summarizer-modes">
                    <button type="button" className={`chat-summarizer-mode-btn${summarizerMode === "free" ? " is-active" : ""}`} onClick={() => setSummarizerMode("free")}>
                      Free (Rule-based)
                    </button>
                    <button type="button" className={`chat-summarizer-mode-btn${summarizerMode === "ai" ? " is-active" : ""}`} onClick={() => setSummarizerMode("ai")}>
                      AI-powered
                    </button>
                  </div>
                  {summarizerMode === "free" && (
                    <div className="chat-summarizer-section">
                      <p className="chat-summarizer-desc">Mechanical summarization. Truncates older messages into bullet points. No API calls, no cost.</p>
                      <label className="chat-summarizer-label">
                        Summarize after
                        <input type="number" min={4} max={50} value={summarizerLimit} onChange={(e) => setSummarizerLimit(Number(e.target.value))} className="chat-summarizer-input" />
                        messages
                      </label>
                    </div>
                  )}
                  {summarizerMode === "ai" && (
                    <div className="chat-summarizer-section">
                      <p className="chat-summarizer-desc">Uses an AI model to generate high-quality summaries. Costs tokens but retains nuance.</p>
                      <label className="chat-summarizer-label">Provider</label>
                      <select className="chat-summarizer-select" value={summarizerProvider} onChange={(e) => {
                        setSummarizerProvider(e.target.value);
                        const group = providerTypes.find((g) => g.type === e.target.value);
                        if (group && group.ids.length > 0) {
                          fetch(`/api/providers/${group.ids[0]}/models`).then((r) => r.json()).then((d) => {
                            setSummarizerModels(d.models ?? []);
                            if (d.models?.length > 0) setSummarizerModel(d.models[0].id);
                          }).catch(() => {});
                        }
                      }}>
                        <option value="">Select provider</option>
                        {providerTypes.map((g) => <option key={g.type} value={g.type}>{g.type.replace("_", " ").toUpperCase()}</option>)}
                      </select>
                      <label className="chat-summarizer-label">Model</label>
                      <select className="chat-summarizer-select" value={summarizerModel} onChange={(e) => setSummarizerModel(e.target.value)}>
                        <option value="">Select model</option>
                        {summarizerModels.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                      </select>
                      {summarizerModel && (() => {
                        const sel = summarizerModels.find((m) => m.id === summarizerModel);
                        const ctx = sel?.context_length;
                        const estimatedMsgs = ctx ? Math.floor(ctx / 800) : null;
                        return (
                          <div className="chat-summarizer-info">
                            {ctx && <span>Context window: {ctx.toLocaleString()} tokens</span>}
                            {estimatedMsgs && <span>Can summarize ~{estimatedMsgs} messages</span>}
                          </div>
                        );
                      })()}
                      <label className="chat-summarizer-label">
                        Summarize after
                        <input type="number" min={4} max={50} value={summarizerLimit} onChange={(e) => setSummarizerLimit(Number(e.target.value))} className="chat-summarizer-input" />
                        messages
                      </label>
                    </div>
                  )}
                  <div className="chat-summarizer-footer">
                    <button type="button" className="chat-summarizer-save" onClick={() => {
                      fetch("/api/settings/summarizer", {
                        method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ mode: summarizerMode, provider: summarizerProvider, model: summarizerModel, limit: summarizerLimit }),
                      }).catch(() => {});
                      setShowSummarizerSettings(false);
                    }}>Save</button>
                  </div>
                </div>
              </div>
            )}
            {showPromptsPopup && (
              <div className="chat-prompts-popup">
                <div className="chat-prompts-popup-inner">
                  <div className="chat-prompts-header">
                    <h4>Prompts / Skills</h4>
                    <button type="button" className="chat-prompts-close" onClick={() => { setShowPromptsPopup(false); setSelectedPromptIds(new Set()); setPromptsSearch(""); }}>x</button>
                  </div>
                  <div className="chat-prompts-modes">
                    <button type="button" className={`chat-prompts-mode-btn${promptsMode === "send" ? " is-active" : ""}`} onClick={() => { setPromptsMode("send"); setSelectedPromptIds(new Set()); }}>Send in Chat</button>
                    <button type="button" className={`chat-prompts-mode-btn${promptsMode === "assign" ? " is-active" : ""}`} onClick={() => { setPromptsMode("assign"); setSelectedPromptIds(new Set()); }}>Assign to Task</button>
                    <button type="button" className={`chat-prompts-mode-btn${promptsMode === "master" ? " is-active" : ""}`} onClick={() => { setPromptsMode("master"); setSelectedPromptIds(new Set()); }}>Master Prompt</button>
                  </div>
                  {promptsMode === "master" && masterPromptId.size > 0 && (
                    <div className="chat-prompts-master-active">
                      Active: <strong>{[...masterPromptId].join(", ")}</strong>
                      <button type="button" onClick={() => { setMasterPromptId(new Set()); }}>Clear</button>
                    </div>
                  )}
                  {promptsMode === "assign" && assignedPromptId.size > 0 && (
                    <div className="chat-prompts-master-active">
                      Assigned: <strong>{[...assignedPromptId].join(", ")}</strong>
                      <button type="button" onClick={() => { setAssignedPromptId(new Set()); }}>Clear</button>
                    </div>
                  )}
                  <input className="chat-prompts-search" type="text" placeholder="Search prompts..." value={promptsSearch} onChange={(e) => { setPromptsSearch(e.target.value); setPromptsHighlight(0); }} autoFocus onKeyDown={(e) => {
                    const filtered = promptsList.filter(p => !promptsSearch || p.name.toLowerCase().includes(promptsSearch.toLowerCase()));
                    if (e.key === "ArrowDown") { e.preventDefault(); setPromptsHighlight(h => Math.min(h + 1, filtered.length - 1)); }
                    else if (e.key === "ArrowUp") { e.preventDefault(); setPromptsHighlight(h => Math.max(h - 1, 0)); }
                    else if (e.key === "ArrowLeft") { e.preventDefault(); setPromptsMode(m => m === "assign" ? "send" : m === "master" ? "assign" : m); }
                    else if (e.key === "ArrowRight") { e.preventDefault(); setPromptsMode(m => m === "send" ? "assign" : m === "assign" ? "master" : m); }
                    else if (e.key === "Enter" && filtered.length > 0) {
                      e.preventDefault();
                      const p = filtered[promptsHighlight];
                      if (!p) return;
                      if (promptsMode === "send") {
                        setSelectedPromptIds(prev => { const n = new Set(prev); if (n.has(p.name)) n.delete(p.name); else n.add(p.name); return n; });
                      } else if (promptsMode === "assign") {
                        setAssignedPromptId(prev => { const n = new Set(prev); if (n.has(p.name)) n.delete(p.name); else n.add(p.name); return n; });
                      } else if (promptsMode === "master") {
                        setMasterPromptId(prev => { const n = new Set(prev); if (n.has(p.name)) n.delete(p.name); else n.add(p.name); return n; });
                      }
                    }
                    else if (e.key === "End" && selectedPromptIds.size > 0) {
                      e.preventDefault();
                      const combined = promptsList.filter(p => selectedPromptIds.has(p.name)).map(p => p.content ?? "").join("\n\n");
                      setInput(prev => prev ? prev + "\n" + combined : combined);
                      setSelectedPromptIds(new Set()); setShowPromptsPopup(false); setPromptsSearch("");
                    }
                    else if (e.key === "Escape") { setShowPromptsPopup(false); setSelectedPromptIds(new Set()); setPromptsSearch(""); }
                  }} />
                  <div className="chat-prompts-list">
                    {promptsList.filter(p => !promptsSearch || p.name.toLowerCase().includes(promptsSearch.toLowerCase())).map((p, i) => {
                      const isSelected = promptsMode === "send" ? selectedPromptIds.has(p.name) : promptsMode === "master" ? masterPromptId.has(p.name) : assignedPromptId.has(p.name);
                      return (
                      <div key={p.id ?? `prompt-${i}`} ref={i === promptsHighlight ? (el) => el?.scrollIntoView({ block: "nearest" }) : undefined} className={`chat-prompts-item${isSelected ? " is-selected" : ""}${i === promptsHighlight ? " is-highlighted" : ""}`} onClick={() => {
                        if (promptsMode === "send") {
                          setSelectedPromptIds(prev => { const n = new Set(prev); if (n.has(p.name)) n.delete(p.name); else n.add(p.name); return n; });
                        } else if (promptsMode === "assign") {
                          setAssignedPromptId(prev => { const n = new Set(prev); if (n.has(p.name)) n.delete(p.name); else n.add(p.name); return n; });
                        } else if (promptsMode === "master") {
                          setMasterPromptId(prev => { const n = new Set(prev); if (n.has(p.name)) n.delete(p.name); else n.add(p.name); return n; });
                        }
                      }}>
                        <span className="chat-prompts-item-name"><span className="chat-prompts-check">{isSelected ? "\u2713" : "\u25CB"}</span>{p.name}</span>
                        <span className="chat-prompts-item-preview">{(p.content ?? "").slice(0, 60)}{(p.content ?? "").length > 60 ? "..." : ""}</span>
                      </div>
                      );
                    })}
                    {promptsList.length === 0 && <div className="chat-prompts-empty">No prompts available. Create them on the Prompts page.</div>}
                  </div>
                  {promptsMode === "send" && selectedPromptIds.size > 0 && (
                    <button type="button" className="chat-prompts-send-btn" onClick={() => {
                      const combined = promptsList.filter(p => selectedPromptIds.has(p.name)).map(p => p.content ?? "").join("\n\n");
                      setInput(prev => prev ? prev + "\n" + combined : combined);
                      setSelectedPromptIds(new Set());
                      setShowPromptsPopup(false);
                    }}>Send Selected ({selectedPromptIds.size})</button>
                  )}
                </div>
              </div>
            )}
            {showRateLimitPopup && (
              <div className="chat-ratelimit-popup">
                <div className="chat-ratelimit-popup-inner">
                  <h4>Rate Limit Reached</h4>
                  <p>The current provider has hit its request limit. You can switch to a different provider or wait a moment before retrying.</p>
                  <div className="chat-ratelimit-actions">
                    <button type="button" className="chat-ratelimit-switch" onClick={() => {
                      setShowRateLimitPopup(false);
                      const currentIdx = providerTypes.findIndex((g) => g.type === selectedProviderType);
                      const nextIdx = (currentIdx + 1) % providerTypes.length;
                      if (providerTypes[nextIdx]) setSelectedProviderType(providerTypes[nextIdx].type);
                    }}>Switch Provider</button>
                    <button type="button" className="chat-ratelimit-wait" onClick={() => {
                      setShowRateLimitPopup(false);
                      setTimeout(() => handleSend(), 5000);
                    }}>Wait & Retry (5s)</button>
                    <button type="button" className="chat-ratelimit-close" onClick={() => setShowRateLimitPopup(false)}>Dismiss</button>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="chat-empty">Select a conversation or start a new one.</div>
        )}
      </main>
    </section>
  );
};
