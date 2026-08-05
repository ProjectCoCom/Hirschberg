/**
 * Summary: Frontend JavaScript/TypeScript module 'Buildterminallist'.
 *
 * What it does: Provides application-level UI helper functions, adapters, or configurations for 'Buildterminallist'.
 *
 * How it fits in: Used to build or bundle the React dashboard application.
 */



import type { TerminalSnapshotReader } from "../ports/TerminalSnapshotReader";

const byCreatedAtAscending = (a: string, b: string): number =>
  new Date(a).getTime() - new Date(b).getTime();

export const buildTerminalList = async (
  reader: TerminalSnapshotReader,
): Promise<Awaited<ReturnType<typeof reader.listTerminalSnapshots>>> => {
  const snapshots = await reader.listTerminalSnapshots();
  return [...snapshots].sort((left, right) =>
    byCreatedAtAscending(left.createdAt, right.createdAt),
  );
};
