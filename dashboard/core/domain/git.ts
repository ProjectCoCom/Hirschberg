/**
 * Summary: Domain model definitions for 'Git'.
 *
 * What it does: Defines TypeScript interfaces, validation types, and helper algorithms for 'Git' model states.
 *
 * How it fits in: Core domain logic consumed by application ports, adapters, and UI presentation views.
 */



import type { TentacleWorkspaceMode } from "./terminal";

export type TentaclePullRequestStatus = "none" | "open" | "merged" | "closed";

export type TentacleGitStatusSnapshot = {
  tentacleId: string;
  workspaceMode: TentacleWorkspaceMode;
  branchName: string;
  upstreamBranchName: string | null;
  isDirty: boolean;
  aheadCount: number;
  behindCount: number;
  insertedLineCount: number;
  deletedLineCount: number;
  hasConflicts: boolean;
  changedFiles: string[];
  defaultBaseBranchName: string | null;
};

export type TentaclePullRequestSnapshot = {
  tentacleId: string;
  workspaceMode: TentacleWorkspaceMode;
  status: TentaclePullRequestStatus;
  number: number | null;
  url: string | null;
  title: string | null;
  baseRef: string | null;
  headRef: string | null;
  isDraft: boolean | null;
  mergeable: "MERGEABLE" | "CONFLICTING" | "UNKNOWN" | null;
  mergeStateStatus: string | null;
};
