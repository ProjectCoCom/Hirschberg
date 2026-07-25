/**
 * Mock server script for dashboard API prototyping.
 *
 * Responsibilities:
 * Spins up an express/node API mock serving pre-packaged dummy metrics and tasks data.
 *
 * Coupling:
 * Used to prototype UI views without running a full SQLite server backend.
 */


import { createServer } from "node:http";
import { WebSocketServer } from "ws";

const PORT = 8787;
const now = () => new Date().toISOString();
const ago = (mins) => new Date(Date.now() - mins * 60_000).toISOString();

// Tentacles = Repos (each ghost node on the graph)
const TENTACLES = [
  {
    tentacleId: "repo-anywebapi",
    displayName: "iceyxsm/AnyWebApi",
    description: "REST API backend — Express + Postgres",
    status: "active",
    color: "#d6a21a",
    octopus: { animation: "walk", expression: "happy", accessory: "none", hairColor: null },
    scope: { paths: ["iceyxsm/AnyWebApi"], tags: ["api", "backend"] },
    vaultFiles: ["CONTEXT.md"],
    todoTotal: 3,
    todoDone: 1,
    todoItems: [
      { text: "Security audit on API endpoints", done: false },
      { text: "Add rate limiting middleware", done: true },
      { text: "Generate API documentation", done: false },
    ],
    suggestedSkills: ["security", "api"],
  },
  {
    tentacleId: "repo-abhiacharyaji",
    displayName: "iceyxsm/Abhiacharyaji",
    description: "React portfolio site with custom sections",
    status: "active",
    color: "#25d366",
    octopus: { animation: "sway", expression: "normal", accessory: "none", hairColor: null },
    scope: { paths: ["iceyxsm/Abhiacharyaji"], tags: ["frontend", "react"] },
    vaultFiles: ["CONTEXT.md"],
    todoTotal: 2,
    todoDone: 0,
    todoItems: [
      { text: "Add unit tests for CustomSection", done: false },
      { text: "Performance optimization", done: false },
    ],
    suggestedSkills: ["testing", "react"],
  },
  {
    tentacleId: "repo-aplisheti",
    displayName: "iceyxsm/ApliSheti",
    description: "Agricultural marketplace — Android + Firebase",
    status: "active",
    color: "#00c8ff",
    octopus: { animation: "jog", expression: "surprised", accessory: "none", hairColor: null },
    scope: { paths: ["iceyxsm/ApliSheti"], tags: ["android", "auth"] },
    vaultFiles: ["CONTEXT.md"],
    todoTotal: 3,
    todoDone: 2,
    todoItems: [
      { text: "JWT authentication", done: false },
      { text: "Schema migration", done: true },
      { text: "Update dependencies", done: true },
    ],
    suggestedSkills: ["authentication", "android"],
  },
  {
    tentacleId: "repo-cplusyait",
    displayName: "OCDDEVS/CplusyAIT",
    description: "C++ AI toolkit with CMake build system",
    status: "active",
    color: "#ff6b2b",
    octopus: { animation: "walk", expression: "angry", accessory: "none", hairColor: null },
    scope: { paths: ["OCDDEVS/CplusyAIT"], tags: ["cpp", "build"] },
    vaultFiles: ["CONTEXT.md"],
    todoTotal: 3,
    todoDone: 0,
    todoItems: [
      { text: "Build system overhaul", done: false },
      { text: "CI pipeline setup", done: false },
      { text: "Fix memory leaks in parser", done: false },
    ],
    suggestedSkills: ["cpp", "cmake"],
  },
  {
    tentacleId: "repo-ekopilot",
    displayName: "StealthIQ/Eko-Pilot-Desktop",
    description: "Electron desktop app — AI coding assistant",
    status: "active",
    color: "#bf5fff",
    octopus: { animation: "sway", expression: "normal", accessory: "none", hairColor: null },
    scope: { paths: ["StealthIQ/Eko-Pilot-Desktop"], tags: ["electron", "desktop"] },
    vaultFiles: ["CONTEXT.md"],
    todoTotal: 2,
    todoDone: 0,
    todoItems: [
      { text: "IPC refactor to contextBridge", done: false },
      { text: "Auto-update integration", done: false },
    ],
    suggestedSkills: ["electron", "ipc"],
  },
  {
    tentacleId: "repo-jatai",
    displayName: "iceyxsm/JAT-AI",
    description: "Jules orchestrator — this project",
    status: "idle",
    color: "#6b7280",
    octopus: { animation: "idle", expression: "sleepy", accessory: "none", hairColor: null },
    scope: { paths: ["iceyxsm/JAT-AI"], tags: ["orchestrator", "python"] },
    vaultFiles: ["CONTEXT.md"],
    todoTotal: 1,
    todoDone: 1,
    todoItems: [
      { text: "README update", done: true },
    ],
    suggestedSkills: ["python", "async"],
  },
];

// Terminals = Agents (session dots hanging off each repo ghost)
const TERMINALS = [
  { terminalId: "agent-01", label: "Security Audit", state: "live", tentacleId: "repo-anywebapi", tentacleName: "Security Audit", workspaceMode: "shared", createdAt: ago(3), agentRuntimeState: "processing", lifecycleState: "running", hasUserPrompt: true },
  { terminalId: "agent-02", label: "Rate Limiting", state: "live", tentacleId: "repo-anywebapi", tentacleName: "Rate Limiting", workspaceMode: "shared", createdAt: ago(8), agentRuntimeState: "processing", lifecycleState: "running", hasUserPrompt: true },
  { terminalId: "agent-03", label: "Unit Tests", state: "live", tentacleId: "repo-abhiacharyaji", tentacleName: "Unit Tests", workspaceMode: "shared", createdAt: ago(5), agentRuntimeState: "processing", lifecycleState: "running", hasUserPrompt: true },
  { terminalId: "agent-04", label: "JWT Auth", state: "live", tentacleId: "repo-aplisheti", tentacleName: "JWT Auth", workspaceMode: "shared", createdAt: ago(7), agentRuntimeState: "processing", lifecycleState: "running", hasUserPrompt: true },
  { terminalId: "agent-05", label: "Build System", state: "live", tentacleId: "repo-cplusyait", tentacleName: "Build System", workspaceMode: "shared", createdAt: ago(4), agentRuntimeState: "processing", lifecycleState: "running", hasUserPrompt: true },
  { terminalId: "agent-06", label: "IPC Refactor", state: "live", tentacleId: "repo-ekopilot", tentacleName: "IPC Refactor", workspaceMode: "shared", createdAt: ago(6), agentRuntimeState: "processing", lifecycleState: "running", hasUserPrompt: true },
  { terminalId: "agent-07", label: "API Docs", state: "queued", tentacleId: "repo-anywebapi", tentacleName: "API Docs", workspaceMode: "shared", createdAt: ago(1), agentRuntimeState: "idle", lifecycleState: "registered" },
  { terminalId: "agent-08", label: "Schema Migration", state: "idle", tentacleId: "repo-aplisheti", tentacleName: "Schema Migration", workspaceMode: "shared", createdAt: ago(30), agentRuntimeState: "idle", lifecycleState: "exited", exitCode: 0, endedAt: ago(28) },
  { terminalId: "agent-09", label: "Update Deps", state: "idle", tentacleId: "repo-aplisheti", tentacleName: "Update Deps", workspaceMode: "shared", createdAt: ago(35), agentRuntimeState: "idle", lifecycleState: "exited", exitCode: 0, endedAt: ago(33) },
  { terminalId: "agent-10", label: "CI Pipeline", state: "queued", tentacleId: "repo-cplusyait", tentacleName: "CI Pipeline", workspaceMode: "shared", createdAt: ago(1), agentRuntimeState: "idle", lifecycleState: "registered" },
  { terminalId: "agent-11", label: "README Update", state: "idle", tentacleId: "repo-jatai", tentacleName: "README Update", workspaceMode: "shared", createdAt: ago(20), agentRuntimeState: "idle", lifecycleState: "exited", exitCode: 0, endedAt: ago(18) },
  { terminalId: "agent-12", label: "Perf Optimization", state: "queued", tentacleId: "repo-abhiacharyaji", tentacleName: "Perf Optimization", workspaceMode: "shared", createdAt: ago(1), agentRuntimeState: "idle", lifecycleState: "registered" },
];

const CONVERSATIONS = {
  sessions: [
    {
      sessionId: "199869604719071891",
      tentacleId: "repo-anywebapi",
      startedAt: ago(15),
      endedAt: ago(12),
      lastEventAt: ago(12),
      eventCount: 8,
      turnCount: 6,
      userTurnCount: 1,
      assistantTurnCount: 5,
      firstUserTurnPreview: "Review API endpoints for security vulnerabilities",
      lastUserTurnPreview: "Review API endpoints for security vulnerabilities",
      lastAssistantTurnPreview: "Found 3 issues. Created REVIEW.md with findings. PR #1 opened.",
    },
    {
      sessionId: "199870112233445566",
      tentacleId: "repo-abhiacharyaji",
      startedAt: ago(5),
      endedAt: null,
      lastEventAt: ago(1),
      eventCount: 4,
      turnCount: 3,
      userTurnCount: 1,
      assistantTurnCount: 2,
      firstUserTurnPreview: "Add comprehensive unit tests for CustomSection component",
      lastUserTurnPreview: "Add comprehensive unit tests for CustomSection component",
      lastAssistantTurnPreview: "Writing test cases for render, props, and event handlers",
    },
    {
      sessionId: "199870223344556677",
      tentacleId: "repo-aplisheti",
      startedAt: ago(7),
      endedAt: null,
      lastEventAt: ago(2),
      eventCount: 3,
      turnCount: 2,
      userTurnCount: 1,
      assistantTurnCount: 1,
      firstUserTurnPreview: "Implement JWT authentication with refresh tokens",
      lastUserTurnPreview: "Implement JWT authentication with refresh tokens",
      lastAssistantTurnPreview: "Setting up auth middleware and token rotation logic",
    },
  ],
};

function getConversationDetail(sessionId) {
  const summary = CONVERSATIONS.sessions.find((s) => s.sessionId === sessionId);
  if (!summary) return null;
  return {
    ...summary,
    turns: [
      { turnId: "t1", role: "user", content: summary.firstUserTurnPreview, startedAt: summary.startedAt, endedAt: summary.startedAt },
      { turnId: "t2", role: "assistant", content: "Analyzing the codebase structure...", startedAt: ago(14), endedAt: ago(14) },
      { turnId: "t3", role: "assistant", content: "Identified key areas. Working on implementation...", startedAt: ago(13), endedAt: ago(13) },
      { turnId: "t4", role: "assistant", content: "Running lint and build checks...", startedAt: ago(12.5), endedAt: ago(12.5) },
      { turnId: "t5", role: "assistant", content: summary.lastAssistantTurnPreview || "Task completed.", startedAt: summary.endedAt || ago(12), endedAt: summary.endedAt || ago(12) },
    ],
    events: [],
  };
}

const CLAUDE_USAGE = {
  status: "ok",
  fetchedAt: now(),
  source: "cli-pty",
  planType: "ultra",
  primaryUsedPercent: 18,
  primaryResetAt: new Date(Date.now() + 6 * 3600_000).toISOString(),
  secondaryUsedPercent: 20,
  secondaryResetAt: null,
  extraUsageCostUsed: 54,
  extraUsageCostLimit: 300,
  message: "54/300 daily sessions | 1/5 accounts (Ultra)",
};

const GITHUB_SUMMARY = {
  status: "ok",
  fetchedAt: now(),
  source: "gh-cli",
  repo: "6 repos active",
  stargazerCount: 12,
  openIssueCount: 3,
  openPullRequestCount: 4,
  commitsPerDay: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 86400_000).toISOString().slice(0, 10),
    count: Math.floor(Math.random() * 15) + 2,
  })),
  recentCommits: [
    { hash: "94b9f6e", shortHash: "94b9f6e", subject: "Fix SQL injection in /api/users", authorName: "jules[bot]", authorEmail: "jules@google.com", authoredAt: ago(120), body: "", filesChanged: 1, insertions: 12, deletions: 8 },
    { hash: "3d24117", shortHash: "3d24117", subject: "Add rate limiting middleware", authorName: "jules[bot]", authorEmail: "jules@google.com", authoredAt: ago(180), body: "", filesChanged: 3, insertions: 66, deletions: 18 },
    { hash: "a1b2c3d", shortHash: "a1b2c3d", subject: "Add unit tests for CustomSection", authorName: "jules[bot]", authorEmail: "jules@google.com", authoredAt: ago(200), body: "", filesChanged: 2, insertions: 95, deletions: 0 },
    { hash: "e4f5g6h", shortHash: "e4f5g6h", subject: "Migrate schema to v2", authorName: "jules[bot]", authorEmail: "jules@google.com", authoredAt: ago(250), body: "", filesChanged: 4, insertions: 42, deletions: 15 },
    { hash: "923effd", shortHash: "923effd", subject: "Wire context store into session runner", authorName: "iceyxsm", authorEmail: "iceyxsm@users.noreply.github.com", authoredAt: ago(300), body: "", filesChanged: 5, insertions: 180, deletions: 30 },
  ],
};

const USAGE_HEATMAP = {
  days: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 86400_000).toISOString().slice(0, 10),
    totalTokens: Math.floor(Math.random() * 50000),
    sessions: Math.floor(Math.random() * 10) + 1,
    projects: [
      { key: "iceyxsm/AnyWebApi", tokens: Math.floor(Math.random() * 20000) },
      { key: "iceyxsm/Abhiacharyaji", tokens: Math.floor(Math.random() * 15000) },
      { key: "iceyxsm/ApliSheti", tokens: Math.floor(Math.random() * 10000) },
    ],
    models: [
      { key: "jules-ultra", tokens: Math.floor(Math.random() * 40000) },
      { key: "jules-pro", tokens: Math.floor(Math.random() * 10000) },
    ],
  })),
  projects: ["iceyxsm/AnyWebApi", "iceyxsm/Abhiacharyaji", "iceyxsm/ApliSheti"],
  models: ["jules-ultra", "jules-pro"],
};

const MONITOR_FEED = {
  providerId: "x",
  queryTerms: ["jules ai", "google jules", "ai coding agent"],
  refreshPolicy: { maxCacheAgeMs: 3600000, maxPosts: 30, searchWindowDays: 7 },
  lastFetchedAt: ago(5),
  staleAfter: new Date(Date.now() + 3600_000).toISOString(),
  isStale: false,
  lastError: null,
  posts: [],
  usage: { status: "ok", source: "x-api", fetchedAt: now(), cap: 500, used: 12, remaining: 488, resetAt: new Date(Date.now() + 86400_000).toISOString() },
};

const MONITOR_CONFIG = {
  providerId: "x",
  queryTerms: ["jules ai", "google jules"],
  refreshPolicy: { maxCacheAgeMs: 3600000, maxPosts: 30, searchWindowDays: 7 },
  providers: { x: { credentials: { isConfigured: false, bearerTokenHint: null, apiKeyHint: null, hasApiSecret: false, hasAccessToken: false, hasAccessTokenSecret: false, updatedAt: null } } },
};

const UI_STATE = {
  activePrimaryNav: 1,
  sidebarWidth: 260,
  isAgentsSidebarVisible: true,
  isRuntimeStatusStripVisible: true,
  isBottomTelemetryVisible: false,
  isMonitorVisible: true,
  minimizedTerminalIds: [],
  isActiveAgentsSectionExpanded: true,
  isClaudeUsageSectionExpanded: true,
  isCodexUsageSectionExpanded: false,
  terminalCompletionSound: "none",
  canvasOpenTerminalIds: [],
  canvasOpenTentacleIds: [],
  canvasTerminalsPanelWidth: null,
};

const ROUTES = {
  "GET /api/terminal-snapshots": () => TERMINALS,
  "GET /api/terminals": () => TERMINALS,
  "GET /api/deck/tentacles": () => TENTACLES,
  "GET /api/deck/skills": () => [
    { name: "security", description: "Security vulnerability scanning", source: "project" },
    { name: "testing", description: "Unit and integration testing", source: "project" },
    { name: "build-systems", description: "Build tooling and CI/CD", source: "user" },
  ],
  "GET /api/conversations": () => CONVERSATIONS,
  "GET /api/ui-state": () => UI_STATE,
  "GET /api/setup": () => ({ shouldShowSetupCard: false, steps: [] }),
  "GET /api/claude/usage": () => CLAUDE_USAGE,
  "GET /api/codex/usage": () => ({ status: "unavailable", fetchedAt: now(), source: "none" }),
  "GET /api/github/summary": () => GITHUB_SUMMARY,
  "GET /api/analytics/usage-heatmap": () => USAGE_HEATMAP,
  "GET /api/code-intel/events": () => ({ events: [] }),
  "GET /api/monitor/feed": () => MONITOR_FEED,
  "GET /api/monitor/config": () => MONITOR_CONFIG,
};

const server = createServer((req, res) => {
  const method = req.method;
  const url = req.url?.split("?")[0] ?? "";
  const key = `${method} ${url}`;

  if (req.headers.upgrade === "websocket") return;

  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Accept");

  if (method === "OPTIONS") { res.writeHead(204); res.end(); return; }

  const convMatch = url.match(/^\/api\/conversations\/([^/]+)$/);
  if (convMatch && method === "GET") {
    const detail = getConversationDetail(decodeURIComponent(convMatch[1]));
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(detail || { error: "not found" }));
    return;
  }

  const promptMatch = url.match(/^\/api\/prompts\/([^/]+)$/);
  if (promptMatch && method === "GET") {
    const name = decodeURIComponent(promptMatch[1]);
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ name, source: "user", content: "" }));
    return;
  }

  if (key === "GET /api/prompts") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ prompts: [] }));
    return;
  }

  const handler = ROUTES[key];
  if (handler) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(handler()));
    return;
  }

  if (method === "POST" || method === "PATCH" || method === "PUT" || method === "DELETE") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  res.writeHead(200, { "Content-Type": "application/json" });
  res.end("[]");
});

const wss = new WebSocketServer({ server });
wss.on("connection", (ws) => {
  const interval = setInterval(() => {
    const t = TERMINALS[Math.floor(Math.random() * TERMINALS.length)];
    ws.send(JSON.stringify({
      type: "terminal-state-changed",
      terminalId: t.terminalId,
      agentRuntimeState: t.agentRuntimeState,
    }));
  }, 30000);
  ws.on("close", () => clearInterval(interval));
});

server.listen(PORT, () => {
  console.log(`JAT-AI mock API: http://127.0.0.1:${PORT}`);
  console.log(`Repos: ${TENTACLES.length} | Agents: ${TERMINALS.length}`);
});
