/**
 * Frontend JavaScript/TypeScript module 'Terminalsnapshotreader'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Terminalsnapshotreader'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


import type { TerminalSnapshot } from "../domain/terminal";

export interface TerminalSnapshotReader {
  listTerminalSnapshots(): Promise<TerminalSnapshot[]>;
}
