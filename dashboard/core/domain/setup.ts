/**
 * Summary: Domain model definitions for 'Setup'.
 *
 * What it does: Defines TypeScript interfaces, validation types, and helper algorithms for 'Setup' model states.
 *
 * How it fits in: Core domain logic consumed by application ports, adapters, and UI presentation views.
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
