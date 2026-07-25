/**
 * Frontend JavaScript/TypeScript module 'Terminalruntimestatestore'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Terminalruntimestatestore'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


export type TerminalRuntimeStateStore = {
  setRuntimeState: (id: string, state: any) => void;
  getRuntimeState: (id: string) => any;
  subscribe: (cb: () => void) => () => void;
  getSnapshot: () => Record<string, any>;
};

export function createTerminalRuntimeStateStore(): TerminalRuntimeStateStore {
  const states: Record<string, any> = {};
  const listeners = new Set<() => void>();
  return {
    setRuntimeState(id, state) {
      states[id] = state;
      listeners.forEach((cb) => cb());
    },
    getRuntimeState(id) {
      return states[id] ?? null;
    },
    subscribe(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    getSnapshot() {
      return { ...states };
    },
  };
}

export type TerminalRuntimeStateInfo = {
  state: string;
  toolName?: string;
};

const EMPTY_MAP = new Map<string, TerminalRuntimeStateInfo>();

export function useTerminalRuntimeStates(
  _store: TerminalRuntimeStateStore,
  _terminalIds: string[],
): Map<string, TerminalRuntimeStateInfo> {
  return EMPTY_MAP;
}

export function getTerminalRuntimeStateInfo(_snapshot: any): TerminalRuntimeStateInfo {
  return { state: "idle" };
}

export function stripTerminalRuntimeState(snapshot: any): any {
  return snapshot;
}

export function stripTerminalRuntimeStates(snapshots: any[]): any[] {
  return snapshots;
}
