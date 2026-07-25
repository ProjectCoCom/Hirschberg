/**
 * Frontend JavaScript/TypeScript module 'Inmemoryterminalsnapshotreader'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Inmemoryterminalsnapshotreader'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


import type { TerminalSnapshot } from "../domain/terminal";
import type { TerminalSnapshotReader } from "../ports/TerminalSnapshotReader";

export class InMemoryTerminalSnapshotReader implements TerminalSnapshotReader {
  constructor(private readonly snapshots: TerminalSnapshot[]) {}

  async listTerminalSnapshots(): Promise<TerminalSnapshot[]> {
    return this.snapshots;
  }
}
