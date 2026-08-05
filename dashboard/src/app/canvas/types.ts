/**
 * Summary: Frontend JavaScript/TypeScript module 'Types'.
 *
 * What it does: Provides application-level UI helper functions, adapters, or configurations for 'Types'.
 *
 * How it fits in: Used to build or bundle the React dashboard application.
 */



import type {
  AgentRuntimeState,
  AgentState,
  DeckOctopusAppearance,
  TentacleWorkspaceMode,
} from "@octogent/core";

export type GraphNode = {
  id: string;
  type: "tentacle" | "octoboss" | "active-session" | "inactive-session";
  x: number;
  y: number;
  vx: number;
  vy: number;
  pinned: boolean;
  radius: number;
  tentacleId: string;
  label: string;
  color: string;
  sessionId?: string;
  agentState?: AgentState;
  agentRuntimeState?: AgentRuntimeState;
  waitingToolName?: string;
  hasUserPrompt?: boolean;
  workspaceMode?: TentacleWorkspaceMode;
  parentTerminalId?: string;
  firstPromptPreview?: string;
  octopus?: DeckOctopusAppearance;
};

export type GraphEdge = {
  source: string;
  target: string;
};
