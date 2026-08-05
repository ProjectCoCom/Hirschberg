/**
 * Summary: Frontend JavaScript/TypeScript module 'App'.
 *
 * What it does: Provides application-level UI helper functions, adapters, or configurations for 'App'.
 *
 * How it fits in: Used to build or bundle the React dashboard application.
 */



import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { useBackendLivenessPolling } from "./app/hooks/useBackendLivenessPolling";
import { OCTOBOSS_ID } from "./app/hooks/useCanvasGraphData";
import { useClaudeUsagePolling } from "./app/hooks/useClaudeUsagePolling";
import { useCodexUsagePolling } from "./app/hooks/useCodexUsagePolling";
import { useConsoleKeyboardShortcuts } from "./app/hooks/useConsoleKeyboardShortcuts";
import { useGitHubPrimaryViewModel } from "./app/hooks/useGitHubPrimaryViewModel";
import { useGithubSummaryPolling } from "./app/hooks/useGithubSummaryPolling";
import { useLiveTaskStatus } from "./app/hooks/useLiveTaskStatus";
import { useMonitorRuntime } from "./app/hooks/useMonitorRuntime";
import { usePersistedUiState } from "./app/hooks/usePersistedUiState";
import { useTentacleGitLifecycle } from "./app/hooks/useTentacleGitLifecycle";
import { useUsageHeatmapPolling } from "./app/hooks/useUsageHeatmapPolling";
import { useWorkspaceSetup } from "./app/hooks/useWorkspaceSetup";
import { clampSidebarWidth } from "./app/uiStateNormalizers";
import { ActiveAgentsSidebar } from "./components/ActiveAgentsSidebar";
import { ConsolePrimaryNav } from "./components/ConsolePrimaryNav";
import { PrimaryViewRouter } from "./components/PrimaryViewRouter";
import { RuntimeStatusStrip } from "./components/RuntimeStatusStrip";
import { SidebarActionPanel } from "./components/SidebarActionPanel";
import { TelemetryTape } from "./components/TelemetryTape";
import { ToastNotification, type Toast } from "./components/ToastNotification";

const EMPTY_COLUMNS: never[] = [];

export const App = () => {
  const [hoveredGitHubOverviewPointIndex, setHoveredGitHubOverviewPointIndex] = useState<
    number | null
  >(null);
  const [deckSidebarContent, setDeckSidebarContent] = useState<ReactNode>(null);
  const [conversationsSidebarContent, setConversationsSidebarContent] = useState<ReactNode>(null);
  const [conversationsActionPanel, setConversationsActionPanel] = useState<ReactNode>(null);
  const [promptsSidebarContent, setPromptsSidebarContent] = useState<ReactNode>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const liveTasks = useLiveTaskStatus();
  const prevTaskStatusRef = useRef<Record<string, string>>({});

  useEffect(() => {
    const prev = prevTaskStatusRef.current;
    for (const task of liveTasks) {
      const oldStatus = prev[task.id];
      if (oldStatus && oldStatus !== task.status) {
        if (task.status === "completed") {
          setToasts((t) => [...t, { id: `t-${Date.now()}-${task.id}`, message: `Task completed: ${task.repo_name}`, type: "success" }]);
        } else if (task.status === "failed") {
          setToasts((t) => [...t, { id: `t-${Date.now()}-${task.id}`, message: `Task failed: ${task.repo_name}`, type: "error" }]);
        }
      }
    }
    prevTaskStatusRef.current = Object.fromEntries(liveTasks.map((t) => [t.id, t.status]));
  }, [liveTasks]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const {
    activePrimaryNav,
    setActivePrimaryNav,
    applyHydratedUiState,
    isActiveAgentsSectionExpanded,
    isAgentsSidebarVisible,
    isBottomTelemetryVisible,
    isClaudeUsageSectionExpanded,
    isCodexUsageSectionExpanded,
    isMonitorVisible,
    isRuntimeStatusStripVisible,
    isUiStateHydrated,
    minimizedTerminalIds,
    readUiState,
    setIsActiveAgentsSectionExpanded,
    setIsAgentsSidebarVisible,
    setIsBottomTelemetryVisible,
    setIsClaudeUsageSectionExpanded,
    setIsCodexUsageSectionExpanded,
    setIsMonitorVisible,
    setIsRuntimeStatusStripVisible,
    setIsUiStateHydrated,
    setMinimizedTerminalIds,
    setSidebarWidth,
    setTerminalCompletionSound,
    sidebarWidth,
    terminalCompletionSound,
    canvasOpenTerminalIds,
    setCanvasOpenTerminalIds,
    canvasOpenTentacleIds,
    setCanvasOpenTentacleIds,
    canvasTerminalsPanelWidth,
    setCanvasTerminalsPanelWidth,
  } = usePersistedUiState({ columns: EMPTY_COLUMNS });

  const {
    workspaceSetup,
    isWorkspaceSetupLoading,
    workspaceSetupError,
    refreshWorkspaceSetup,
    runWorkspaceSetupStep,
  } = useWorkspaceSetup();

  // The UI state endpoint returns static defaults — mark as hydrated immediately
  useEffect(() => { setIsUiStateHydrated(true); }, [setIsUiStateHydrated]);

  const [runningWorkspaceSetupStepId, setRunningWorkspaceSetupStepId] = useState<
    | "initialize-workspace"
    | "ensure-gitignore"
    | "check-claude"
    | "check-git"
    | "check-curl"
    | "create-tentacles"
    | null
  >(null);

  const {
    gitStatusByTentacleId,
    gitStatusLoadingByTentacleId,
    pullRequestByTentacleId,
    pullRequestLoadingByTentacleId,
    openGitTentacleId,
    openGitTentacleStatus,
    openGitTentaclePullRequest,
    gitCommitMessageDraft,
    gitDialogError,
    isGitDialogLoading,
    isGitDialogMutating,
    setGitCommitMessageDraft,
    openTentacleGitActions,
    closeTentacleGitActions,
    commitTentacleChanges,
    commitAndPushTentacleBranch,
    pushTentacleBranch,
    syncTentacleBranch,
    mergeTentaclePullRequest,
  } = useTentacleGitLifecycle({
    columns: EMPTY_COLUMNS,
  });

  const { codexUsageSnapshot, refreshCodexUsage } = useCodexUsagePolling();
  const { claudeUsageSnapshot, isRefreshingClaudeUsage, refreshClaudeUsage } =
    useClaudeUsagePolling();
  const backendLivenessStatus = useBackendLivenessPolling();
  const { githubRepoSummary, isRefreshingGitHubSummary, refreshGitHubRepoSummary } =
    useGithubSummaryPolling();

  const { heatmapData, isLoadingHeatmap, refreshHeatmap } = useUsageHeatmapPolling({
    enabled: isUiStateHydrated && (activePrimaryNav === 3 || isRuntimeStatusStripVisible),
  });

  useConsoleKeyboardShortcuts({ setActivePrimaryNav });

  useEffect(() => {
    const handler = (e: Event) => {
      const nav = (e as CustomEvent).detail;
      if (typeof nav === "number") setActivePrimaryNav(nav);
    };
    window.addEventListener("navigate", handler);
    return () => window.removeEventListener("navigate", handler);
  }, [setActivePrimaryNav]);

  const monitorRuntime = useMonitorRuntime({
    enabled: isUiStateHydrated && isMonitorVisible,
  });

  const {
    githubCommitCount30d,
    sparklinePoints,
    githubOverviewGraphSeries,
    githubOverviewGraphPolylinePoints,
    githubOverviewHoverLabel,
    githubStatusPill,
    githubRepoLabel,
    githubStarCountLabel,
    githubOpenIssuesLabel,
    githubOpenPrsLabel,
    githubRecentCommits,
  } = useGitHubPrimaryViewModel({
    githubRepoSummary,
    hoveredGitHubOverviewPointIndex,
    setHoveredGitHubOverviewPointIndex,
  });

  const hasSidebarActionPanel =
    conversationsActionPanel !== null ||
    (openGitTentacleId !== null);

  const sidebarActionPanel = hasSidebarActionPanel ? (
    conversationsActionPanel ? (
      <>{conversationsActionPanel}</>
    ) : (
      <SidebarActionPanel
        pendingDeleteTerminal={null}
        isDeletingTerminalId={null}
        clearPendingDeleteTerminal={() => {}}
        confirmDeleteTerminal={async () => {}}
        openGitTentacleId={openGitTentacleId}
        columns={[]}
        openGitTentacleStatus={openGitTentacleStatus}
        openGitTentaclePullRequest={openGitTentaclePullRequest}
        gitCommitMessageDraft={gitCommitMessageDraft}
        gitDialogError={gitDialogError}
        isGitDialogLoading={isGitDialogLoading}
        isGitDialogMutating={isGitDialogMutating}
        setGitCommitMessageDraft={setGitCommitMessageDraft}
        closeTentacleGitActions={closeTentacleGitActions}
        commitTentacleChanges={commitTentacleChanges}
        commitAndPushTentacleBranch={commitAndPushTentacleBranch}
        pushTentacleBranch={pushTentacleBranch}
        syncTentacleBranch={syncTentacleBranch}
        mergeTentaclePullRequest={mergeTentaclePullRequest}
        requestDeleteTerminal={() => {}}
      />
    )
  ) : null;

  useEffect(() => {
    if (!hasSidebarActionPanel || isAgentsSidebarVisible) {
      return;
    }
    setIsAgentsSidebarVisible(true);
  }, [isAgentsSidebarVisible, setIsAgentsSidebarVisible, hasSidebarActionPanel]);

  const handleRunWorkspaceSetupStep = useCallback(
    async (
      stepId:
        | "initialize-workspace"
        | "ensure-gitignore"
        | "check-claude"
        | "check-git"
        | "check-curl"
        | "create-tentacles",
    ) => {
      setRunningWorkspaceSetupStepId(stepId);
      try {
        await runWorkspaceSetupStep(stepId);
      } finally {
        setRunningWorkspaceSetupStepId(null);
      }
    },
    [runWorkspaceSetupStep],
  );

  return (
    <div className="page console-shell">
      {isRuntimeStatusStripVisible && (
        <RuntimeStatusStrip
          sparklinePoints={sparklinePoints}
          usageData={heatmapData}
          claudeUsage={claudeUsageSnapshot}
          isRefreshingClaudeUsage={isRefreshingClaudeUsage}
          onRefreshClaudeUsage={refreshClaudeUsage}
        />
      )}

      <ConsolePrimaryNav
        activePrimaryNav={activePrimaryNav}
        onPrimaryNavChange={setActivePrimaryNav}
      />

      <section className="console-main-canvas" aria-label="Main content canvas">
        <div
          className={`workspace-shell${isAgentsSidebarVisible && activePrimaryNav !== 1 && activePrimaryNav !== 2 && activePrimaryNav !== 3 && activePrimaryNav !== 4 && activePrimaryNav !== 6 && activePrimaryNav !== 7 && activePrimaryNav !== 8 ? "" : " workspace-shell--full"}`}
        >
          {isAgentsSidebarVisible &&
            activePrimaryNav !== 1 &&
            activePrimaryNav !== 2 &&
            activePrimaryNav !== 3 &&
            activePrimaryNav !== 4 &&
            activePrimaryNav !== 6 &&
            activePrimaryNav !== 7 &&
            activePrimaryNav !== 8 && (
              <ActiveAgentsSidebar
                sidebarWidth={sidebarWidth}
                onSidebarWidthChange={(width) => {
                  setSidebarWidth(clampSidebarWidth(width));
                }}
                actionPanel={sidebarActionPanel}
                bodyContent={
                  activePrimaryNav === 2
                    ? (deckSidebarContent ?? undefined)
                    : activePrimaryNav === 4
                      ? (conversationsSidebarContent ?? undefined)
                      : activePrimaryNav === 5
                        ? (promptsSidebarContent ?? undefined)
                        : undefined
                }
              />
            )}

          <PrimaryViewRouter
            activePrimaryNav={activePrimaryNav}
            isMonitorVisible={isMonitorVisible}
            activityPrimaryViewProps={{
              usageChartProps: {
                data: heatmapData,
                isLoading: isLoadingHeatmap,
                onRefresh: refreshHeatmap,
              },
              githubPrimaryViewProps: {
                githubCommitCount30d,
                githubOpenIssuesLabel,
                githubOpenPrsLabel,
                githubRecentCommits,
                githubOverviewGraphPolylinePoints,
                githubOverviewGraphSeries,
                githubOverviewHoverLabel,
                githubRepoLabel,
                githubStarCountLabel,
                githubStatusPill,
                hoveredGitHubOverviewPointIndex,
                isRefreshingGitHubSummary,
                onHoveredGitHubOverviewPointIndexChange: setHoveredGitHubOverviewPointIndex,
                onRefresh: () => {
                  void refreshGitHubRepoSummary();
                },
              },
            }}
            monitorRuntime={monitorRuntime}
            settingsPrimaryViewProps={{
              isMonitorVisible,
              isRuntimeStatusStripVisible,
              onMonitorVisibilityChange: setIsMonitorVisible,
              onRuntimeStatusStripVisibilityChange: setIsRuntimeStatusStripVisible,
            }}
            canvasPrimaryViewProps={{
              columns: EMPTY_COLUMNS,
              runtimeStateStore: undefined,
              isUiStateHydrated,
              recentlyCreatedTerminal: null,
              canvasOpenTerminalIds,
              canvasOpenTentacleIds,
              canvasTerminalsPanelWidth,
              workspaceSetup,
              isWorkspaceSetupLoading,
              workspaceSetupError,
              runningWorkspaceSetupStepId,
              onRunWorkspaceSetupStep: handleRunWorkspaceSetupStep,
              onLaunchWorkspaceSetupPlanner: async () => {
                const response = await fetch("/api/terminals", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    name: "tentacle-planner",
                    workspaceMode: "shared",
                    agentProvider: "claude-code",
                    promptTemplate: "tentacle-planner",
                  }),
                });
                if (!response.ok) {
                  return undefined;
                }
                const snapshot = (await response.json()) as { terminalId?: string };
                if (typeof snapshot.terminalId !== "string") {
                  return undefined;
                }
                return snapshot.terminalId;
              },
              onCanvasOpenTerminalIdsChange: setCanvasOpenTerminalIds,
              onCanvasOpenTentacleIdsChange: setCanvasOpenTentacleIds,
              onCanvasTerminalsPanelWidthChange: setCanvasTerminalsPanelWidth,
              onCreateAgent: async (_tentacleId) => {
                return undefined;
              },
              onCreateTerminal: async () => {
                return undefined;
              },
              onCreateWorktreeTerminal: async () => {
                return undefined;
              },
              onCreateTentacle: async () => {
                const response = await fetch("/api/deck/tentacles", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ name: "", description: "" }),
                });
                if (!response.ok) return;
              },
              onSpawnSwarm: async (tentacleId, workspaceMode) => {
                const response = await fetch(
                  `/api/deck/tentacles/${encodeURIComponent(tentacleId)}/swarm`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ workspaceMode }),
                  },
                );
                if (!response.ok) return;
              },
              onOctobossAction: async (action) => {
                const response = await fetch("/api/terminals", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    workspaceMode: "shared",
                    tentacleId: OCTOBOSS_ID,
                    promptTemplate: action,
                  }),
                });
                if (!response.ok) return undefined;
                const snapshot = (await response.json()) as { terminalId?: string };
                return typeof snapshot.terminalId === "string" ? snapshot.terminalId : undefined;
              },
              onTentacleAction: async (tentacleId, action) => {
                const response = await fetch("/api/terminals", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    workspaceMode: "shared",
                    tentacleId,
                    promptTemplate: action,
                    promptVariables: {
                      tentacleId,
                    },
                  }),
                });
                if (!response.ok) return undefined;
                const snapshot = (await response.json()) as { terminalId?: string };
                return typeof snapshot.terminalId === "string" ? snapshot.terminalId : undefined;
              },
              onNavigateToConversation: (_sessionId) => {
                setActivePrimaryNav(4);
              },
              onCloseActiveSession: (_terminalId, _terminalName, _workspaceMode) => {},
              onDeleteActiveSession: (_terminalId, _terminalName, _workspaceMode) => {},
              pendingDeleteTerminal: null,
              isDeletingTerminalId: null,
              onCancelDelete: () => {},
              onConfirmDelete: () => {},
              onTerminalRenamed: (_terminalId: string, _tentacleName: string) => {},
              onTerminalActivity: (_terminalId: string) => {},
              onRefreshColumns: async () => {},
            }}
            conversationsEnabled={isUiStateHydrated && activePrimaryNav === 4}
            onConversationsSidebarContent={setConversationsSidebarContent}
            onConversationsActionPanel={setConversationsActionPanel}
            promptsEnabled={true}
            onPromptsSidebarContent={setPromptsSidebarContent}
          />
        </div>
      </section>

      {isUiStateHydrated && isMonitorVisible && isBottomTelemetryVisible && (
        <TelemetryTape monitorFeed={monitorRuntime.monitorFeed} />
      )}

      <ToastNotification toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
