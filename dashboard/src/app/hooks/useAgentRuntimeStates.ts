/**
 * Summary: Custom React hook 'Useagentruntimestates'.
 *
 * What it does: Abstracts state management, data polling, or backend API actions for 'Useagentruntimestates' into a reusable hook.
 *
 * How it fits in: Consumed by React UI components inside the 'dashboard/src/components' component tree.
 */



import { useMemo } from "react";

import {
  type TerminalRuntimeStateInfo,
  type TerminalRuntimeStateStore,
  useTerminalRuntimeStates,
} from "../terminalRuntimeStateStore";
import type { TerminalView } from "../types";

export type AgentRuntimeStateInfo = TerminalRuntimeStateInfo;

export const useAgentRuntimeStates = (
  runtimeStateStore: TerminalRuntimeStateStore,
  columns: TerminalView,
): Map<string, AgentRuntimeStateInfo> => {
  const terminalIds = useMemo(() => columns.map((column) => column.terminalId), [columns]);
  return useTerminalRuntimeStates(runtimeStateStore, terminalIds);
};
