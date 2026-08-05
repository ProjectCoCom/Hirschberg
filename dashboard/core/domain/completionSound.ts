/**
 * Summary: Domain model definitions for 'Completionsound'.
 *
 * What it does: Defines TypeScript interfaces, validation types, and helper algorithms for 'Completionsound' model states.
 *
 * How it fits in: Core domain logic consumed by application ports, adapters, and UI presentation views.
 */



export const TERMINAL_COMPLETION_SOUND_IDS = [
  "soft-chime",
  "retro-beep",
  "double-beep",
  "bell",
  "pop",
  "silent",
] as const;

export type TerminalCompletionSoundId = (typeof TERMINAL_COMPLETION_SOUND_IDS)[number];

export const isTerminalCompletionSoundId = (value: unknown): value is TerminalCompletionSoundId =>
  typeof value === "string" &&
  TERMINAL_COMPLETION_SOUND_IDS.includes(value as TerminalCompletionSoundId);
