/**
 * Summary: Domain model definitions for 'Agentruntime'.
 *
 * What it does: Defines TypeScript interfaces, validation types, and helper algorithms for 'Agentruntime' model states.
 *
 * How it fits in: Core domain logic consumed by application ports, adapters, and UI presentation views.
 */



export type AgentRuntimeState =
  | "idle"
  | "processing"
  | "waiting_for_permission"
  | "waiting_for_user";

export const isAgentRuntimeState = (value: unknown): value is AgentRuntimeState =>
  value === "idle" ||
  value === "processing" ||
  value === "waiting_for_permission" ||
  value === "waiting_for_user";

export type TerminalAgentProvider = "codex" | "claude-code";

export const TERMINAL_AGENT_PROVIDERS: TerminalAgentProvider[] = ["codex", "claude-code"];

export const isTerminalAgentProvider = (value: unknown): value is TerminalAgentProvider =>
  typeof value === "string" && TERMINAL_AGENT_PROVIDERS.includes(value as TerminalAgentProvider);
