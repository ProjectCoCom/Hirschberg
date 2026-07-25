/**
 * Frontend JavaScript/TypeScript module 'Notificationsounds'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Notificationsounds'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


export type TerminalCompletionSoundId = "none" | "chime" | "bell";

export const DEFAULT_TERMINAL_COMPLETION_SOUND: TerminalCompletionSoundId = "none";

export const TERMINAL_COMPLETION_SOUND_OPTIONS: { id: TerminalCompletionSoundId; label: string; description: string }[] = [];

export function isTerminalCompletionSoundId(value: unknown): value is TerminalCompletionSoundId {
  return value === "none" || value === "chime" || value === "bell";
}
