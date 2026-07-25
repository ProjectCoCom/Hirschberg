/**
 * Domain model definitions for 'Setup'.
 *
 * Responsibilities:
 * Defines TypeScript interfaces, validation types, and helper algorithms for 'Setup' model states.
 *
 * Coupling:
 * Core domain logic consumed by application ports, adapters, and UI presentation views.
 */


export type WorkspaceSetupStepId =
  | "initialize-workspace"
  | "ensure-gitignore"
  | "check-claude"
  | "check-git"
  | "check-curl"
  | "create-tentacles";

export type WorkspaceSetupStep = {
  id: WorkspaceSetupStepId;
  title: string;
  description: string;
  complete: boolean;
  required: boolean;
  actionLabel: string | null;
  statusText: string;
  guidance: string | null;
  command: string | null;
};

export type WorkspaceSetupSnapshot = {
  isFirstRun: boolean;
  shouldShowSetupCard: boolean;
  hasAnyTentacles: boolean;
  tentacleCount: number;
  steps: WorkspaceSetupStep[];
};
