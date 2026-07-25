/**
 * Frontend JavaScript/TypeScript module 'Types'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Types'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


import type { GitHubCommitPoint, buildTerminalList } from "@octogent/core";

export type TerminalView = Awaited<ReturnType<typeof buildTerminalList>>;

export type {
  CodexUsageSnapshot,
  ClaudeUsageSnapshot,
  GitHubCommitPoint,
  GitHubRecentCommit,
  GitHubRepoSummarySnapshot,
  TerminalAgentProvider,
  TentacleGitStatusSnapshot,
  TentaclePullRequestSnapshot,
  MonitorUsageSnapshot,
  MonitorPost,
  MonitorConfigSnapshot,
  MonitorFeedSnapshot,
  ConversationTurn,
  ConversationTranscriptEvent,
  ConversationSessionSummary,
  ConversationSessionDetail,
  ConversationSearchHit,
} from "@octogent/core";

export type { PersistedUiState as FrontendUiStateSnapshot } from "@octogent/core";
export type { TentacleWorkspaceMode as TerminalWorkspaceMode } from "@octogent/core";

export type GitHubCommitSparkPoint = GitHubCommitPoint & {
  x: number;
  y: number;
};

export type PromptLibraryEntry = {
  name: string;
  source: "builtin" | "user" | "system";
};

export type PromptDetail = {
  name: string;
  source: "builtin" | "user" | "system";
  content: string;
};
