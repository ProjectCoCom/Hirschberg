/**
 * Summary: Frontend JavaScript/TypeScript module 'Terminalsnapshotreader'.
 *
 * What it does: Provides application-level UI helper functions, adapters, or configurations for 'Terminalsnapshotreader'.
 *
 * How it fits in: Used to build or bundle the React dashboard application.
 */



import type { TerminalSnapshot } from "../domain/terminal";

export interface TerminalSnapshotReader {
  listTerminalSnapshots(): Promise<TerminalSnapshot[]>;
}
