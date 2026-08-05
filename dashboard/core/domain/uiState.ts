/**
 * Summary: Domain model definitions for 'Uistate'.
 *
 * What it does: Defines TypeScript interfaces, validation types, and helper algorithms for 'Uistate' model states.
 *
 * How it fits in: Core domain logic consumed by application ports, adapters, and UI presentation views.
 */



import type { TerminalCompletionSoundId } from "./completionSound";

export type PersistedUiState = {
  activePrimaryNav?: number;
  isAgentsSidebarVisible?: boolean;
  sidebarWidth?: number;
  isActiveAgentsSectionExpanded?: boolean;
  isRuntimeStatusStripVisible?: boolean;
  isMonitorVisible?: boolean;
  isBottomTelemetryVisible?: boolean;
  isCodexUsageVisible?: boolean;
  isClaudeUsageVisible?: boolean;
  isClaudeUsageSectionExpanded?: boolean;
  isCodexUsageSectionExpanded?: boolean;
  terminalCompletionSound?: TerminalCompletionSoundId;
  minimizedTerminalIds?: string[];
  terminalWidths?: Record<string, number>;
  canvasOpenTerminalIds?: string[];
  canvasOpenTentacleIds?: string[];
  canvasTerminalsPanelWidth?: number;
  terminalInactivityThresholdMs?: number;
};
